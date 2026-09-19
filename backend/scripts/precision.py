#!/usr/bin/env python
"""Score precision on a fixed set of real pull requests, every round, the same way.

The corpus in tests/prompt_corpus.py measures recall: a planted bug, does the
reviewer find it. This measures the other half on code nobody planted anything
in: of the findings the pipeline posts on eleven real pull requests, how many
would make a competent maintainer change something. There is no answer key for
a real pull request, so the answer key is two independent judges and a ledger
that grows: tests/precision/pull_requests.json pins the set, and
tests/precision/judgements.json holds two verdicts per finding, keyed by a
fingerprint of the path, the title and the evidence, so a finding judged once
is never judged again.

Usage, from backend/ with the venv:
    .venv/bin/python scripts/precision.py run --out ~/ReviewBot-runs/<date>/precision-runs --tag round1 \
        --model qwen3.5:9b --cross-model gemma4:12b --unload
    .venv/bin/python scripts/precision.py run --from-database ./reviews.db \
        --out ~/ReviewBot-runs/<date>/precision-runs --tag round0
    .venv/bin/python scripts/precision.py sheet ~/ReviewBot-runs/<date>/precision-runs round0 --out ~/ReviewBot-runs/<date>
    .venv/bin/python scripts/precision.py merge ~/ReviewBot-runs/<date>/round0-judge-a.json ~/ReviewBot-runs/<date>/round0-judge-b.json
    .venv/bin/python scripts/precision.py score ~/ReviewBot-runs/<date>/precision-runs round0 [--markdown]
    .venv/bin/python scripts/precision.py replay ~/ReviewBot-runs/<date>/precision-runs round1 \
        --out ~/ReviewBot-runs/<date>/precision-runs --tag-out round1-after

`run` is the only subcommand that needs Ollama, and only without
--from-database, which builds round 0 out of the findings already stored in
reviews.db with no model at all. `replay` pushes a round's recorded replies
back through the current pipeline, so a post-filter change is scored on real
code with nothing loaded. The protocol the judges follow, and the rolling
table of rounds, is docs/benchmarks/PRECISION.md."""

import argparse
import asyncio
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

for _var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY", "LANGCHAIN_API_KEY",
             "LANGSMITH_API_KEY", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING", "LANGSMITH_TRACING_V2",
             "LANGCHAIN_TRACING", "LANGCHAIN_HANDLER", "SENTRY_DSN"):
    os.environ.pop(_var, None)
# config.settings builds a module-level Settings on import and insists on the App's secrets; the
# harness never uses them, so placeholders stand in (a private key that really parses, because the
# validator signs with it). The harness's own Settings is built in settings_for.
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

_THROWAWAY_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
# DATABASE_URL is :memory: deliberately: nothing here reaches the App's database through Settings,
# because --from-database is a filesystem path opened read-only by read_database, so no subcommand
# can later be added that quietly reads an empty database instead of the measurement
_PLACEHOLDERS = {"GITHUB_APP_ID": "1", "GITHUB_PRIVATE_KEY": _THROWAWAY_KEY,
                 "GITHUB_WEBHOOK_SECRET": "precision-not-a-secret-0123456789",
                 "LOCAL_API_TOKEN": "", "DATABASE_URL": "sqlite:///:memory:"}
for _key, _value in _PLACEHOLDERS.items():
    os.environ.setdefault(_key, _value)

import logging  # noqa: E402

from langchain_core.callbacks import BaseCallbackHandler  # noqa: E402
from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402

from config.settings import LocalOnlyViolation, Settings  # noqa: E402
from services.ai_reviewer import FileReviewer, FileReviewResult, parse_file_review, postprocess  # noqa: E402
from services.diff import parse_patch  # noqa: E402
from services.git_diff import GITHUB_CONTEXT_LINES, split_git_diff  # noqa: E402
from services.llm import build_chat_model, ollama_health, unload_model  # noqa: E402
from services.review_runner import prepare_files, select_files  # noqa: E402

PR_SET = BACKEND / "tests" / "precision" / "pull_requests.json"
LEDGER = BACKEND / "tests" / "precision" / "judgements.json"

# The diff of a range, pinned: hunk boundaries and therefore every finding's line number depend on
# the context size and on the prefixes, so a machine with its own diff configuration must still get
# the bytes the reviewer saw. Three-dot, because the bases are derived from the shape of the stack
# rather than from merge commits and `git merge-base --is-ancestor` fails for them.
GIT_DIFF = ["git", "--no-pager", "-C", str(REPO),
            "-c", "core.quotepath=false", "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false",
            "-c", "diff.relative=false", "-c", "diff.renames=true",
            "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--find-renames",
            f"--unified={GITHUB_CONTEXT_LINES}", "--src-prefix=a/", "--dst-prefix=b/"]

REASON_CATEGORIES = ("wrong_about_code", "style_preference", "untouched_line", "defence_as_attack",
                     "instruction_title", "other")
VERDICTS = ("real", "not_real")
JUDGEMENT_FIELDS = ("fingerprint", "pull_requests", "path", "line", "category", "title", "evidence",
                    "first_seen", "judges")
JUDGE_FIELDS = ("judge", "verdict", "reason_category", "reason", "date")
DROP_RULES = ("confidence", "tag_title", "praise", "unlocated", "duplicate")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CannotRun(Exception):
    """A reason a subcommand cannot start; printed to stderr, exit code 2."""


# ---------------------------------------------------------------- git and the set


def git(*args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, check=False)
    except FileNotFoundError:
        raise CannotRun("git is not on PATH")
    if done.returncode != 0:
        raise CannotRun(f"git {' '.join(args)} failed: {done.stderr.decode('utf-8', errors='replace').strip()}")
    return done.stdout.decode("utf-8", errors="replace")


def diff_text(base: str, head: str) -> str:
    """The three-dot diff of one pull request's range. Both ends are checked
    first, because git answers a missing commit in the symmetric form with
    "Invalid symmetric difference expression" and names neither sha, so the
    shallow-checkout hint would never fire and nothing would say which end of
    the range this machine does not hold."""
    for sha in (base, head):
        try:
            done = subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", f"{sha}^{{commit}}"],
                                  capture_output=True, check=False)
        except FileNotFoundError:
            raise CannotRun("git is not on PATH")
        if done.returncode != 0:
            raise CannotRun(f"{sha} is not a commit in this checkout (a shallow checkout does not hold it)")
    try:
        done = subprocess.run(GIT_DIFF + [f"{base}...{head}", "--"], capture_output=True, check=False)
    except FileNotFoundError:
        raise CannotRun("git is not on PATH")
    if done.returncode != 0:
        raise CannotRun(f"git diff {base}...{head} failed: {done.stderr.decode('utf-8', errors='replace').strip()}")
    return done.stdout.decode("utf-8", errors="replace")


def pipeline_commit() -> Tuple[str, bool]:
    """The commit the pipeline was at, and whether the tree was dirty."""
    try:
        return git("rev-parse", "HEAD").strip(), bool(git("status", "--porcelain").strip())
    except CannotRun:
        return "", False


def load_set() -> Dict[str, Any]:
    return json.loads(PR_SET.read_text(encoding="utf-8"))


def entries_for(fixed: Dict[str, Any], only: str) -> List[Dict[str, Any]]:
    """The rows --only names, or all of them. A value that is not a number, or a
    --only that names nothing at all, is a mistyped command line rather than a
    round over the whole set, so it is refused instead of quietly running all
    eleven or raising ValueError out of main."""
    rows = list(fixed["pull_requests"])
    if not only:
        return rows
    wanted = set()
    for part in only.replace(" ", "").split(","):
        if not part:
            continue
        try:
            wanted.add(int(part))
        except ValueError:
            raise CannotRun(f"--only {part!r} is not a pull request number")
    if not wanted:
        raise CannotRun(f"--only {only!r} names no pull request")
    chosen = [r for r in rows if r["number"] in wanted]
    missing = sorted(wanted - {r["number"] for r in chosen})
    if missing:
        raise CannotRun(f"--only names pull requests the set does not hold: {missing}")
    return chosen


# ---------------------------------------------------------------- the fingerprint


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalise_title(title: str) -> str:
    """Lower case, whitespace collapsed, surrounding quotes and backticks and
    trailing sentence punctuation gone, and the kind inside a redaction marker
    forgotten as normalise_evidence forgets it, because a model quotes the line
    into its title too and services/redaction.py names the kind: the same claim
    retyped is one claim."""
    t = _collapse(title).strip("`\"'").strip()
    t = re.sub(r"\[REDACTED:[^\]]*\]", "[REDACTED]", t)
    return _collapse(t.rstrip(".,:;!?")).lower()


def normalise_evidence(evidence: str) -> str:
    """Whitespace collapsed, the two quote marks made one as services/diff.py:68-71
    does, a leading diff marker dropped as :74-81 does, and the kind inside a
    redaction marker forgotten, because services/redaction.py:126 names the kind
    and a later pattern could name it differently for the same line. Case is
    kept: two lines that differ only in case are two lines."""
    ev = _collapse((evidence or "").replace('"', "'"))
    if ev and ev[0] in "+- " and len(ev) > 1:
        ev = _collapse(ev[1:])
    return re.sub(r"\[REDACTED:[^\]]*\]", "[REDACTED]", ev)


def fingerprint(path: str, title: str, evidence: str) -> str:
    """What makes two findings the same finding. The pull request number is
    deliberately not in it: the same claim about the same line of the same file
    is one judgement wherever it turns up, so a ledger entry carries a list of
    the pull requests it has been seen on and the per-pull-request table is
    driven by the run records instead."""
    material = f"{path}\n{normalise_title(title)}\n{normalise_evidence(evidence)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- the ledger


def load_ledger(path: Optional[Path] = None) -> Dict[str, Any]:
    """The ledger, validated on the way in. save_ledger validates before a
    write, but a ledger can also be edited by hand or land through a merge
    conflict, and an entry with one judge would otherwise still produce a
    number: every subcommand that reads a verdict reads it through here."""
    # the module global is read at call time, not bound as a default, so a test can point the
    # harness at a ledger in a temporary directory without writing to the committed one
    path = LEDGER if path is None else path
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"version": 1, "judgements": []}
    try:
        numbers: Optional[List[int]] = [r["number"] for r in load_set()["pull_requests"]]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        numbers = None  # the fixed set is unreadable, so the pull request numbers go unchecked
    bad = validate_ledger(data, numbers)
    if bad:
        raise CannotRun(f"the ledger at {path} is not valid:\n  " + "\n  ".join(bad))
    return data


def validate_ledger(data: Dict[str, Any], numbers: Optional[Sequence[int]] = None) -> List[str]:
    """Everything wrong with a ledger, as sentences. An empty ledger is valid,
    so the branch is mergeable before any judging has happened."""
    bad: List[str] = []
    if not isinstance(data, dict):
        return ["the ledger is not a JSON object"]
    if data.get("version") != 1:
        bad.append(f"version is {data.get('version')!r}, not 1")
    for key in data:
        if key not in ("version", "judgements"):
            bad.append(f"unknown key {key!r} at the top level")
    entries = data.get("judgements")
    if not isinstance(entries, list):
        return bad + ["judgements is not a list"]
    seen: Dict[str, int] = {}
    for i, e in enumerate(entries):
        where = f"judgement {i}"
        if not isinstance(e, dict):
            bad.append(f"{where} is not an object")
            continue
        fp = e.get("fingerprint", "")
        where = f"judgement {fp or i}"
        for field in JUDGEMENT_FIELDS:
            if field not in e:
                bad.append(f"{where} is missing {field}")
        for key in e:
            if key not in JUDGEMENT_FIELDS:
                bad.append(f"{where} has the unknown key {key!r}")
        if fp in seen:
            bad.append(f"{where} appears twice, at {seen[fp]} and {i}")
        elif fp:
            seen[fp] = i
        if all(k in e for k in ("path", "title", "evidence")):
            own = fingerprint(e["path"], e["title"], e["evidence"])
            if own != fp:
                bad.append(f"{where} does not match its own path, title and evidence (that fingerprints to {own})")
        prs = e.get("pull_requests")
        if not isinstance(prs, list) or not prs:
            bad.append(f"{where} names no pull request")
        elif numbers is not None:
            for n in prs:
                if n not in numbers:
                    bad.append(f"{where} names pull request {n}, which the fixed set does not hold")
        judges = e.get("judges")
        if not isinstance(judges, list) or len(judges) != 2:
            bad.append(f"{where} has {0 if not isinstance(judges, list) else len(judges)} judges, not exactly two")
            judges = judges if isinstance(judges, list) else []
        names = []
        for j in judges:
            if not isinstance(j, dict):
                bad.append(f"{where} has a judge that is not an object")
                continue
            for field in JUDGE_FIELDS:
                if field not in j:
                    bad.append(f"{where} has a judge missing {field}")
            for key in j:
                if key not in JUDGE_FIELDS:
                    bad.append(f"{where} has a judge with the unknown key {key!r}")
            names.append(j.get("judge", ""))
            if j.get("verdict") not in VERDICTS:
                bad.append(f"{where}: verdict {j.get('verdict')!r} from {j.get('judge')!r} is not real or not_real")
            if j.get("verdict") == "not_real" and j.get("reason_category") not in REASON_CATEGORIES:
                bad.append(f"{where}: a not_real verdict from {j.get('judge')!r} needs a reason_category from "
                           f"{', '.join(REASON_CATEGORIES)}, not {j.get('reason_category')!r}")
            if j.get("verdict") == "real" and j.get("reason_category") not in ("", None):
                bad.append(f"{where}: a real verdict from {j.get('judge')!r} carries the reason_category "
                           f"{j.get('reason_category')!r}; a reason category explains a not_real verdict")
            if not _DATE.match(str(j.get("date", ""))):
                bad.append(f"{where}: the date {j.get('date')!r} from {j.get('judge')!r} is not YYYY-MM-DD")
        if len(names) == 2 and names[0] == names[1]:
            bad.append(f"{where}: {names[0]!r} judged it twice, which is one judge and not two")
    return bad


def save_ledger(data: Dict[str, Any], path: Optional[Path] = None, numbers: Optional[Sequence[int]] = None) -> None:
    """Sorted so a diff of the ledger reads in pull request order, and validated
    again before the write returns. backend/ is in .prettierignore, so nothing
    else ever reformats this file."""
    data["judgements"] = sorted(data.get("judgements", []),
                                key=lambda e: (min(e.get("pull_requests") or [0]), e.get("path", ""), e.get("title", "")))
    bad = validate_ledger(data, numbers)
    if bad:
        raise CannotRun("refusing to write an invalid ledger:\n  " + "\n  ".join(bad))
    (LEDGER if path is None else path).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def judged_by(ledger: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {e["fingerprint"]: e for e in ledger.get("judgements", []) if e.get("fingerprint")}


def verdict_of(entry: Dict[str, Any]) -> str:
    """real when both judges said real, not_real when both said not_real,
    disputed when they disagree."""
    said = {j.get("verdict") for j in entry.get("judges", [])}
    return said.pop() if len(said) == 1 else "disputed"


# ---------------------------------------------------------------- settings and models


def settings_for(model: Optional[str] = None, cross_model: Optional[str] = None, max_files: Optional[int] = None,
                 min_confidence: Optional[float] = None, num_ctx: Optional[int] = None) -> Settings:
    """The harness's own Settings, built through the constructor and ignoring
    backend/.env. Both model tags go in this way rather than through model_copy
    so that refuse_to_leak (config/settings.py:236-262) judges them: this reads
    real code, so a cloud tag is refused and there is no way round it.

    The verify pass is deliberately not a parameter: its reply sits between the
    reviewer's and the cross-examiner's in a record's model_texts, so a round
    recorded with it on cannot be replayed. VERIFY_FINDINGS in the environment
    still reaches these settings for anyone who wants such a round anyway."""
    env: Dict[str, Any] = dict(_PLACEHOLDERS)
    env["STRICT_LOCAL"] = "true"
    if model:
        env["OLLAMA_MODEL"] = model
    if cross_model is not None:
        env["CROSS_EXAMINE_MODEL"] = cross_model
    if max_files is not None:
        env["MAX_FILES_PER_REVIEW"] = max_files
    if min_confidence is not None:
        env["MIN_FINDING_CONFIDENCE"] = min_confidence
    if num_ctx is not None:
        env["OLLAMA_NUM_CTX"] = num_ctx
    try:
        return Settings(_env_file=None, **env)
    except LocalOnlyViolation as refused:
        raise CannotRun(f"refused by the local-only guard: {refused} (these are real code diffs, so there is no "
                        f"--allow-cloud here)")
    except ValueError as invalid:
        raise CannotRun(f"settings are invalid: {invalid}")


class Recorder(BaseCallbackHandler):
    """Keeps every raw model reply, in order, so a round can be re-scored later
    without the model. Same shape as scripts/prompt_eval.py:151-163."""

    def __init__(self) -> None:
        self.texts: List[str] = []

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        try:
            gen = response.generations[0][0]
            msg = getattr(gen, "message", None)
            self.texts.append(msg.content if msg is not None else gen.text)
        except (IndexError, AttributeError):
            self.texts.append("")


class ReplayFileModel(BaseChatModel):
    """Answers with the reply a recorded round has for this pull request and
    file, so `replay` pushes a round through a changed pipeline with no model
    loaded at all. Same shape as scripts/prompt_eval.py:166-186, keyed by file
    rather than by corpus case. It is never asked for a key it lacks, because
    replay skips a file that recorded no reply."""

    model: str
    texts: Dict[str, str]  # "<pr>:<filename>" -> the raw reply
    key: str = ""

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        msg = AIMessage(content=self.texts[self.key],
                        usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        return "precision-replay"


# ---------------------------------------------------------------- one review


def classify_raw(raw_text: str, patch: str, min_confidence: float) -> Tuple[int, Dict[str, int]]:
    """How many findings the model raised and which rule removed each one that
    did not survive, counted by the postprocess itself rather than by a copy of
    its loop: the copy applied drop_rule and then the locator, and missed the
    instruction-title retitle that sits between them, so its duplicate key was
    the title the model typed and not the title the pipeline kept. A round can
    then say whether a finding vanished through a rule or because the model
    never raised it. Every rule services/ai_reviewer.py names has a counter
    here, and a test holds the two lists equal."""
    review, _ = parse_file_review(raw_text)
    drops = {rule: 0 for rule in DROP_RULES}
    postprocess(review, patch, min_confidence, counts=drops)
    return len(review.findings), drops


def finding_row(path: str, f: Any) -> Dict[str, Any]:
    """One finding as the database stores it (services/review_runner.py:186-193),
    plus the fingerprint the ledger is keyed by."""
    return {"path": path, "line": f.line, "category": f.category.value, "severity": f.severity.value,
            "source_model": getattr(f, "source_model", None) or None,
            "cross_verdict": getattr(f, "cross_verdict", None),
            "cross_reason": getattr(f, "cross_reason", "") or None,
            "title": f.title, "evidence": f.evidence, "recommendation": f.recommendation,
            "confidence": f.confidence, "fingerprint": fingerprint(path, f.title, f.evidence)}


async def review_files(files: List[Dict[str, Any]], reviewer: FileReviewer, recorder: Recorder, settings: Settings,
                       key_for: Optional[Callable[[str], None]] = None,
                       unload: Optional[Callable[[str], Any]] = None) -> Tuple[List[FileReviewResult], Dict[str, List[str]]]:
    """Every prepared file through the reviewer, then, when a cross-examiner is
    configured, every result through it in a second phase, which is what the
    reference laptop needs: one model resident at a time. The per-review call
    budgets are reset first, because both are per review and one reviewer
    serving eleven pull requests would otherwise run out part way through and
    the later rounds would quietly measure the reviewer alone."""
    reviewer.cross_budget = settings.CROSS_EXAMINE_MAX_CALLS_PER_REVIEW
    reviewer.verify_budget = settings.MAX_VERIFY_CALLS_PER_REVIEW
    if reviewer.cross_enabled:
        reviewer.cross_inline = False  # this loop runs the second phase itself
    texts: Dict[str, List[str]] = {}
    results: List[FileReviewResult] = []
    for f in files:
        if key_for:
            key_for(f["filename"])
        before = len(recorder.texts)
        result = await reviewer.review_file(f["filename"], f["language"], f["status"], f["patch"])
        texts[f["filename"]] = list(recorder.texts[before:])
        results.append(result)
    if reviewer.cross_enabled:
        if unload is not None:
            await unload(settings.OLLAMA_MODEL)
        for result in results:
            if key_for:
                key_for(result.filename)
            before = len(recorder.texts)
            await reviewer.cross_examine_file(result)
            texts.setdefault(result.filename, []).extend(recorder.texts[before:])
    return results, texts


async def review_pull_request(entry: Dict[str, Any], text: str, reviewer: FileReviewer, recorder: Recorder,
                              settings: Settings, unload: Optional[Callable[[str], Any]] = None,
                              key_for: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """One pull request, from its diff text rather than its sha range, so the
    one git call lives in `run` and both the tests and `replay` can drive this
    with a literal diff and need neither git nor a model."""
    started = time.perf_counter()
    raw_files = split_git_diff(text)
    selected, skipped = select_files(raw_files, settings)
    files, _ = prepare_files(selected)
    results, texts = await review_files(files, reviewer, recorder, settings, key_for=key_for, unload=unload)
    record = new_record(entry, settings, model=reviewer.model_name)
    record["split"] = len(raw_files)
    record["skipped"] = [{"path": p, "reason": r} for p, r in skipped]
    fill_record(record, files, results, texts, settings.MIN_FINDING_CONFIDENCE)
    record["seconds"] = round(time.perf_counter() - started, 1)
    return record


def new_record(entry: Dict[str, Any], settings: Settings, model: str = "", cross_model: str = "") -> Dict[str, Any]:
    commit, dirty = pipeline_commit()
    return {
        "tag": "", "repository": "", "pr": entry["number"], "title": entry.get("title", ""),
        "base_sha": entry["base_sha"], "head_sha": entry["head_sha"],
        "model": model or settings.OLLAMA_MODEL,
        "cross_model": cross_model or (settings.CROSS_EXAMINE_MODEL or None),
        "settings": {"max_files_per_review": settings.MAX_FILES_PER_REVIEW,
                     "min_finding_confidence": settings.MIN_FINDING_CONFIDENCE,
                     "verify_findings": settings.VERIFY_FINDINGS,
                     "ollama_num_ctx": settings.OLLAMA_NUM_CTX,
                     "max_patch_bytes": settings.MAX_PATCH_BYTES,
                     "cross_examine_max_calls_per_review": settings.CROSS_EXAMINE_MAX_CALLS_PER_REVIEW},
        "pipeline_commit": commit, "pipeline_dirty": dirty,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "seconds": 0.0, "replayable": True,
        "split": 0, "files": [], "skipped": [], "errored": [], "findings": [],
    }


def fill_record(record: Dict[str, Any], files: List[Dict[str, Any]], results: List[FileReviewResult],
                texts: Dict[str, List[str]], min_confidence: float) -> None:
    """The per-file rows, the errored files and the findings. Errored files are
    kept apart from skipped ones, because reviews.skipped mixes the two (a file
    the model answered unusably is written into the same list by
    services/review_runner.py:259, which is why PR 24's recorded skip set has
    four entries where select_files yields three)."""
    patches = {f["filename"]: f["patch"] for f in files}
    for r in results:
        raw_texts = texts.get(r.filename) or []
        raw, drops = classify_raw(raw_texts[0] if raw_texts else "", patches.get(r.filename, ""), min_confidence)
        record["files"].append({
            "filename": r.filename, "language": r.language, "status": r.status,
            "additions": next((f.get("additions", 0) for f in files if f["filename"] == r.filename), 0),
            "patch": patches.get(r.filename, ""), "model_texts": raw_texts, "raw": raw, "drops": drops,
            "prompt_tokens": r.prompt_tokens, "output_tokens": r.output_tokens,
            "seconds": round(r.duration_seconds, 1), "parse_ok": r.parse_ok, "error": r.error,
        })
        if not (r.parse_ok and not r.error):
            record["errored"].append({"path": r.filename,
                                      "reason": f"the model did not return a usable review ({r.error or 'unreadable reply'})"})
            continue
        for f in r.review.findings:
            record["findings"].append(finding_row(r.filename, f))


# ---------------------------------------------------------------- records on disk


def write_record(out: Path, tag: str, repository: str, record: Dict[str, Any]) -> Path:
    record["tag"], record["repository"] = tag, repository
    path = out / f"{tag}-pr{record['pr']:02d}.json"
    path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return path


def load_records(runs: str, tag: str) -> List[Dict[str, Any]]:
    directory = Path(runs).expanduser()
    if not directory.is_dir():
        raise CannotRun(f"{runs} is not a directory")
    paths = sorted(directory.glob(f"{tag}-pr*.json"))
    if not paths:
        raise CannotRun(f"no record of the tag {tag!r} in {runs} (expected {tag}-pr<NN>.json)")
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def refuse_out_inside_repo(out: str) -> Path:
    """A record holds real code and every raw model reply, so it lives outside
    the repository, the rule docs/benchmarks/README.md states for prompt runs."""
    path = Path(out).expanduser().resolve()
    if path == REPO or REPO in path.parents:
        raise CannotRun(f"--out {path} is inside the repository working tree; a record holds real code and every raw "
                        f"model reply, so write it somewhere like ~/ReviewBot-runs/<date>/precision-runs")
    return path


# ---------------------------------------------------------------- run


DB_QUERY = """select r.pr_number, r.head_sha, r.model, r.cross_model, r.started_at, r.duration_seconds,
       f.path, f.line, f.category, f.severity, f.title, f.evidence, f.recommendation, f.confidence,
       f.source_model, f.cross_verdict, f.cross_reason, r.id, r.created_at
from findings f join reviews r on f.review_id = r.id
where r.repository = ? and r.pr_number between 23 and 33 and r.status = 'completed'
order by r.pr_number, r.created_at, f.path, f.line"""


def _query_database(uri: str, repository: str) -> List[Any]:
    conn = sqlite3.connect(uri, uri=True)
    try:
        return list(conn.execute(DB_QUERY, (repository,)))
    finally:
        conn.close()


def read_database(path: str, repository: str) -> Tuple[Dict[int, List[Dict[str, Any]]], Dict[int, Dict[str, Any]]]:
    """The stored findings of the set, read once, read-only, so the file cannot
    be touched: scripts/export_reviews.py is deliberately not used here, because
    its init_db opens the URL read-write, sets PRAGMA journal_mode=WAL and then
    runs create_all and the ALTER TABLE migrations on the only surviving copy of
    the 2026-09-07 measurement.

    mode=ro alone, and not immutable=1, because the App keeps the database in
    write-ahead logging mode and immutable=1 tells SQLite to ignore the log, so
    a review that is still only in reviews.db-wal would silently not be in the
    round. A WAL database whose directory cannot take the -shm file cannot be
    opened that way at all, and that is the one case immutable=1 is fallen back
    to, with a line to stderr saying what is then invisible."""
    file = Path(path).expanduser()
    if not file.is_file():
        raise CannotRun(f"--from-database {path} is not a file")
    try:
        rows = _query_database(f"file:{file}?mode=ro", repository)
    except sqlite3.OperationalError as e:
        print(f"{path} could not be opened read-only ({e}); falling back to immutable=1, so any row still in the "
              f"write-ahead log is invisible to this round", file=sys.stderr)
        try:
            rows = _query_database(f"file:{file}?mode=ro&immutable=1", repository)
        except sqlite3.DatabaseError as again:
            raise CannotRun(f"could not read {path}: {again}")
    except sqlite3.DatabaseError as e:
        raise CannotRun(f"could not read {path}: {e}")
    return _by_pull_request(rows)


def _by_pull_request(rows: List[Any]) -> Tuple[Dict[int, List[Dict[str, Any]]], Dict[int, Dict[str, Any]]]:
    """The rows as findings and metadata per pull request. Today each pull
    request of the set has exactly one completed review, but a re-review would
    add another and the two would be read as one round's findings, so only the
    most recent by created_at is kept and the rest are named on stderr."""
    reviews: Dict[int, Dict[str, List[Any]]] = {}
    created: Dict[Tuple[int, str], str] = {}
    for r in rows:
        pr, review_id = int(r[0]), str(r[17])
        reviews.setdefault(pr, {}).setdefault(review_id, []).append(r)
        created[(pr, review_id)] = str(r[18] or "")
    findings: Dict[int, List[Dict[str, Any]]] = {}
    meta: Dict[int, Dict[str, Any]] = {}
    for pr, per_review in sorted(reviews.items()):
        if len(per_review) > 1:
            newest = max(per_review, key=lambda rid: (created[(pr, rid)], rid))
            print(f"pr {pr}: {len(per_review)} completed reviews hold findings; keeping the one created "
                  f"{created[(pr, newest)] or 'last'} and skipping {len(per_review) - 1}", file=sys.stderr)
            per_review = {newest: per_review[newest]}
        kept_rows = next(iter(per_review.values()))
        for r in kept_rows:
            meta.setdefault(pr, {"head_sha": r[1], "model": r[2], "cross_model": r[3], "started_at": r[4],
                                 "seconds": round(float(r[5] or 0), 1)})
            findings.setdefault(pr, []).append({
                "path": r[6], "line": r[7], "category": r[8], "severity": r[9], "source_model": r[14],
                "cross_verdict": r[15], "cross_reason": r[16], "title": r[10], "evidence": r[11],
                "recommendation": r[12], "confidence": r[13],
                "fingerprint": fingerprint(r[6], r[10], r[11]),
            })
    return findings, meta


def database_record(entry: Dict[str, Any], text: str, settings: Settings, findings: List[Dict[str, Any]],
                    meta: Dict[str, Any]) -> Dict[str, Any]:
    """Round 0 for one pull request: the findings as the database holds them,
    with the patches regenerated and redacted so a judge reading the sheet sees
    the lines the model saw. No model runs, nothing was recorded on the night
    beyond the findings themselves, so the record says replayable false."""
    raw_files = split_git_diff(text)
    selected, skipped = select_files(raw_files, settings)
    files, _ = prepare_files(selected)
    record = new_record(entry, settings, model=meta.get("model") or "", cross_model=meta.get("cross_model") or "")
    record["split"] = len(raw_files)
    record["skipped"] = [{"path": p, "reason": r} for p, r in skipped]
    record["started_at"] = str(meta.get("started_at") or "")
    record["seconds"] = meta.get("seconds", 0.0)
    record["replayable"] = False
    by_path = {f["filename"]: f for f in files}
    for f in files:
        on_file = [row for row in findings if row["path"] == f["filename"]]
        record["files"].append({
            "filename": f["filename"], "language": f["language"], "status": f["status"],
            "additions": f.get("additions", 0), "patch": f["patch"], "model_texts": [],
            "raw": len(on_file), "drops": {rule: 0 for rule in DROP_RULES},
            "prompt_tokens": 0, "output_tokens": 0, "seconds": 0.0, "parse_ok": True, "error": None,
        })
    for row in findings:
        if row["path"] not in by_path:
            print(f"pr {entry['number']}: the stored finding on {row['path']} sits on a file the regenerated diff "
                  f"does not select; the record keeps it with no patch", file=sys.stderr)
        record["findings"].append(dict(row))
    return record


async def cmd_run(args: argparse.Namespace) -> int:
    fixed = load_set()
    entries = entries_for(fixed, args.only)
    out = refuse_out_inside_repo(args.out)
    settings = settings_for(args.model, "" if args.no_cross else args.cross_model, args.max_files,
                            args.min_confidence, args.num_ctx)
    out.mkdir(parents=True, exist_ok=True)
    if args.from_database:
        stored, meta = read_database(args.from_database, fixed["database"]["repository"])
        recorded = fixed.get("recorded_round", {})
        print(f"{args.tag}: {sum(len(v) for v in stored.values())} stored findings over {len(stored)} of the "
              f"{len(entries)} pull requests, read with no model")
        for entry in entries:
            # a pull request whose review stored no finding gets no row out of the join, so its
            # provenance comes from the round the set records rather than from the harness's defaults
            row = dict(meta.get(entry["number"]) or {})
            for field in ("model", "cross_model"):
                if not row.get(field):
                    row[field] = recorded.get(field) or ""
            record = database_record(entry, diff_text(entry["base_sha"], entry["head_sha"]), settings,
                                     stored.get(entry["number"], []), row)
            report_drift(entry, record)
            path = write_record(out, args.tag, fixed["repository"], record)
            print(f"pr {entry['number']:>2}: {len(record['findings'])} findings, "
                  f"{len(record['files'])} files reviewed -> {path.name}")
        return 0

    health = await ollama_health(settings)
    if not health.get("reachable") or not health.get("model_present"):
        print(f"Ollama at {settings.OLLAMA_BASE_URL} is not reachable or {settings.OLLAMA_MODEL} is not pulled: {health}",
              file=sys.stderr)
        return 2
    if settings.CROSS_EXAMINE_MODEL and not health.get("cross_model_present"):
        print(f"the cross-examiner {settings.CROSS_EXAMINE_MODEL} is not pulled: {health}", file=sys.stderr)
        return 2
    llm = build_chat_model(settings)
    recorder = Recorder()
    llm.callbacks = [recorder]
    cross_llm = None
    if settings.CROSS_EXAMINE_MODEL:
        cross_llm = build_chat_model(settings, model=settings.CROSS_EXAMINE_MODEL,
                                     keep_alive=settings.CROSS_EXAMINE_KEEP_ALIVE)
        cross_llm.callbacks = [recorder]
    reviewer = FileReviewer(llm, settings, cross_llm=cross_llm)
    unload = (lambda model: unload_model(settings, model)) if args.unload else None
    print(f"model {settings.OLLAMA_MODEL}"
          + (f", cross-examiner {settings.CROSS_EXAMINE_MODEL}" if settings.CROSS_EXAMINE_MODEL else "")
          + f" at {settings.OLLAMA_BASE_URL}, num_ctx {settings.OLLAMA_NUM_CTX}, {len(entries)} pull requests")
    for entry in entries:
        record = await review_pull_request(entry, diff_text(entry["base_sha"], entry["head_sha"]), reviewer,
                                          recorder, settings, unload=unload)
        report_drift(entry, record)
        path = write_record(out, args.tag, fixed["repository"], record)
        print(f"pr {entry['number']:>2}: {len(record['findings'])} findings from {len(record['files'])} files in "
              f"{record['seconds']:.0f} s -> {path.name}")
    if args.unload and settings.CROSS_EXAMINE_MODEL:
        await unload_model(settings, settings.CROSS_EXAMINE_MODEL)
    return 0


def report_drift(entry: Dict[str, Any], record: Dict[str, Any]) -> None:
    """The split and selected counts against the set, so a diff that is no
    longer the diff the night reviewed is visible before the machine is spent."""
    if record["split"] != entry["files"]:
        print(f"pr {entry['number']}: the range splits into {record['split']} files, the set records "
              f"{entry['files']}", file=sys.stderr)
    reviewed = len(record["files"])
    if reviewed != entry["selected_at_recorded_settings"]:
        print(f"pr {entry['number']}: {reviewed} files selected, the set records "
              f"{entry['selected_at_recorded_settings']}", file=sys.stderr)


# ---------------------------------------------------------------- sheet


Row = Tuple[Dict[str, Any], Dict[str, Any], List[int]]


def unjudged(records: List[Dict[str, Any]], ledger: Dict[str, Any]) -> List[Row]:
    """Every finding nobody has judged, once per fingerprint, with the record it
    was first seen in and every pull request of the round it was seen on: one
    fingerprint on two pull requests is still one judgement, and recording it
    against whichever pull request came first loses the other."""
    known = judged_by(ledger)
    out: List[Row] = []
    at: Dict[str, List[int]] = {}
    for record in records:
        for f in record["findings"]:
            fp = f["fingerprint"]
            if fp in known:
                continue
            if fp in at:
                if record["pr"] not in at[fp]:
                    at[fp].append(record["pr"])
                continue
            at[fp] = [record["pr"]]
            out.append((record, f, at[fp]))
    for _, _, prs in out:
        prs.sort()
    return out


def context_block(patch: str, line: int, span: int) -> str:
    """The new-file lines around a finding, numbered, with the added ones
    marked, read out of the stored patch by the pipeline's own parser."""
    parsed = parse_patch(patch)
    if not parsed.new_lines:
        return "(no patch stored for this file)"
    numbers = sorted(no for no in parsed.new_lines if abs(no - line) <= span)
    rows = []
    for no in numbers:
        mark = "+" if no in parsed.added_lines else " "
        here = " <-- the finding" if no == line else ""
        rows.append(f"{mark} {no:>5}  {parsed.new_lines[no]}{here}")
    return "\n".join(rows) or "(the line the finding names is not in the patch)"


def near_matches(finding: Dict[str, Any], ledger: Dict[str, Any]) -> List[str]:
    """A judged finding on the same file whose normalised evidence or title is
    the same: almost certainly this finding re-fingerprinted, because the
    postprocess retitles an instruction-titled finding and trims multi-line
    evidence to the part it located."""
    out = []
    for e in ledger.get("judgements", []):
        if e.get("path") != finding["path"]:
            continue
        if (normalise_evidence(e.get("evidence", "")) == normalise_evidence(finding["evidence"])
                or normalise_title(e.get("title", "")) == normalise_title(finding["title"])):
            out.append(f"{e['fingerprint']} ({verdict_of(e)}, pull requests {e.get('pull_requests')})")
    return out


def sheet_text(tag: str, rows: List[Row], ledger: Dict[str, Any], span: int) -> str:
    """One sheet for a judge: the table of what is unjudged, then one numbered
    section per finding with its evidence, the model's recommendation and the
    lines around it. The context is a block rather than a table cell because a
    code block cannot sit inside one."""
    out = [f"# Precision sheet: {tag}", "",
           f"{len(rows)} finding{'s' if len(rows) != 1 else ''} nobody has judged. The question for each one: would a "
           "competent maintainer change anything because of it. The protocol is docs/benchmarks/PRECISION.md; fill "
           f"your own copy of {tag}-skeleton.json without reading the other judge's.", "",
           "| # | PR | Path | Line | Category | Severity | Title | Fingerprint |",
           "| - | -- | ---- | ---- | -------- | -------- | ----- | ----------- |"]
    for i, (_, f, prs) in enumerate(rows, start=1):
        out.append(f"| {i} | {', '.join(str(n) for n in prs)} | `{f['path']}` | {f['line']} | {f['category']} | "
                   f"{f['severity']} | {_cell(f['title'])} | `{f['fingerprint']}` |")
    for i, (record, f, prs) in enumerate(rows, start=1):
        out += ["", f"## {i}. `{f['path']}` line {f['line']} ({f['fingerprint']})", "",
                (f"Pull requests {', '.join(str(n) for n in prs)}" if len(prs) > 1
                 else f"Pull request {record['pr']}")
                + f", {record.get('title', '')}. {f['category']}, {f['severity']}, "
                f"confidence {f['confidence']}"
                + (f", raised by {f['source_model']}" if f.get("source_model") else "")
                + (f", cross-examiner said {f['cross_verdict']}" if f.get("cross_verdict") else "") + ".", "",
                f"**{_plain(f['title'])}**", "",
                "Evidence as the model quoted it:", "", "```", _plain(f["evidence"]), "```", "",
                "Recommendation:", "", "> " + _plain(f["recommendation"]).replace("\n", "\n> "), "",
                "The lines around it, added lines marked:", "", "```",
                _plain(context_block(_patch_for(record, f["path"]), f["line"], span)), "```"]
        same = near_matches(f, ledger)
        if same:
            out += ["", "Possibly the same finding as an already judged one, re-fingerprinted: " + ", ".join(same)]
    return "\n".join(out) + "\n"


def _patch_for(record: Dict[str, Any], path: str) -> str:
    return next((f["patch"] for f in record["files"] if f["filename"] == path), "")


def _plain(text: str) -> str:
    """Model text goes into a file a person reads: no control characters, and
    nothing that could close the fence it sits in."""
    cleaned = "".join(ch for ch in str(text or "") if ch in "\n\t" or ch.isprintable())
    return cleaned.replace("```", "'''")


def _cell(text: str) -> str:
    return _plain(text).replace("|", "\\|").replace("\n", " ")[:120]


def skeleton(tag: str, rows: List[Row]) -> Dict[str, Any]:
    """The judge's form. pull_request is the first pull request the round saw the
    finding on and pull_requests is all of them; the ledger stores the list, and
    the single number stays because a judge reads it and an older skeleton
    carries nothing else."""
    return {"run": tag, "judge": "", "date": "",
            "verdicts": [{"fingerprint": f["fingerprint"], "pull_request": record["pr"], "pull_requests": list(prs),
                          "path": f["path"], "line": f["line"], "category": f["category"], "title": f["title"],
                          "evidence": f["evidence"], "verdict": "", "reason_category": "", "reason": ""}
                         for record, f, prs in rows]}


def cmd_sheet(args: argparse.Namespace) -> int:
    records = load_records(args.runs, args.tag)
    ledger = load_ledger()
    rows = unjudged(records, ledger)
    text = sheet_text(args.tag, rows, ledger, args.context)
    if not args.out:
        sys.stdout.write(text)
        return 0
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.tag}-sheet.md").write_text(text, encoding="utf-8")
    (out / f"{args.tag}-skeleton.json").write_text(json.dumps(skeleton(args.tag, rows), indent=1) + "\n",
                                                   encoding="utf-8")
    total = sum(len(r["findings"]) for r in records)
    print(f"{args.tag}: {total} findings in {len(records)} records, {len(rows)} unjudged fingerprints")
    print(f"wrote {out / (args.tag + '-sheet.md')}")
    print(f"wrote {out / (args.tag + '-skeleton.json')}")
    print("copy the skeleton once per judge, fill each without reading the other, then merge")
    return 0


# ---------------------------------------------------------------- merge


def pull_requests_of(verdict: Dict[str, Any]) -> List[int]:
    """The pull requests one filled verdict names: the list a skeleton carries
    now, or the single number one written before the list did."""
    prs = verdict.get("pull_requests")
    if isinstance(prs, list) and prs:
        return sorted({int(n) for n in prs})
    return [int(verdict["pull_request"])] if verdict.get("pull_request") is not None else []


def cmd_merge(args: argparse.Namespace) -> int:
    fixed = load_set()
    numbers = [r["number"] for r in fixed["pull_requests"]]
    ledger = load_ledger()
    known = judged_by(ledger)
    filled: Dict[str, List[Tuple[str, str, Dict[str, Any]]]] = {}
    order: Dict[str, Dict[str, Any]] = {}
    for path in args.filled:
        doc = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
        judge, date, run = doc.get("judge", ""), doc.get("date", ""), doc.get("run", "")
        if not judge or not _DATE.match(str(date)):
            raise CannotRun(f"{path}: fill in judge and a date as YYYY-MM-DD before merging")
        for v in doc.get("verdicts", []):
            fp = v.get("fingerprint", "")
            if not fp:
                raise CannotRun(f"{path}: a verdict with no fingerprint")
            if v.get("verdict") not in VERDICTS:
                raise CannotRun(f"{path}: verdict {v.get('verdict')!r} on {fp} is not real or not_real")
            if v["verdict"] == "not_real" and v.get("reason_category") not in REASON_CATEGORIES:
                raise CannotRun(f"{path}: {fp} is not_real with the reason_category {v.get('reason_category')!r}, "
                                f"which is not one of {', '.join(REASON_CATEGORIES)}")
            if not str(v.get("reason", "")).strip():
                raise CannotRun(f"{path}: {fp} has no reason; one line is the whole ask")
            filled.setdefault(fp, []).append((judge, date, v))
            order.setdefault(fp, {**v, "first_seen": run})
    added = skipped = 0
    for fp, votes in filled.items():
        judges = {j for j, _, _ in votes}
        if len(votes) != 2 or len(judges) != 2:
            raise CannotRun(f"{fp} has {len(votes)} verdicts from {len(judges)} judge(s); the ledger holds exactly two "
                            f"independent judgements per finding")
        v = order[fp]
        prs = pull_requests_of(v)
        if fp in known:
            if not args.skip_existing:
                raise CannotRun(f"{fp} is already in the ledger, judged by "
                                f"{', '.join(j['judge'] for j in known[fp]['judges'])}; pass --skip-existing to add "
                                f"only the pull requests it has now been seen on")
            entry = known[fp]
            for n in prs:
                if n not in entry["pull_requests"]:
                    entry["pull_requests"].append(n)
            entry["pull_requests"].sort()
            skipped += 1
            continue
        ledger["judgements"].append({
            "fingerprint": fp, "pull_requests": prs, "path": v["path"], "line": v["line"],
            "category": v["category"], "title": v["title"], "evidence": v["evidence"],
            "first_seen": v.get("first_seen", ""),
            "judges": [{"judge": judge, "verdict": vote["verdict"],
                        "reason_category": vote.get("reason_category", "") if vote["verdict"] == "not_real" else "",
                        "reason": str(vote.get("reason", "")).strip(), "date": date}
                       for judge, date, vote in votes],
        })
        added += 1
    save_ledger(ledger, numbers=numbers)
    where = str(LEDGER.relative_to(REPO)) if REPO in LEDGER.parents else str(LEDGER)
    print(f"merged {added} new judgement{'s' if added != 1 else ''} into {where}"
          + (f", {skipped} already judged" if skipped else ""))
    for e in sorted(ledger["judgements"], key=lambda e: e["fingerprint"]):
        if e["fingerprint"] in filled and e["fingerprint"] not in known:
            print(f"  {e['fingerprint']} {verdict_of(e):<9} {e['path']}:{e['line']} {_cell(e['title'])}")
    return 0


# ---------------------------------------------------------------- score


def tally(records: List[Dict[str, Any]], ledger: Dict[str, Any]) -> Dict[str, Any]:
    """The round's numbers. Occurrences are findings as the records hold them,
    one per row; a judgement is per fingerprint, so precision is counted over
    distinct fingerprints and the occurrence count is printed beside it."""
    known = judged_by(ledger)
    occurrences = [(r, f) for r in records for f in r["findings"]]
    fingerprints: Dict[str, List[int]] = {}
    for r, f in occurrences:
        fingerprints.setdefault(f["fingerprint"], []).append(r["pr"])
    judged = {fp: known[fp] for fp in fingerprints if fp in known}
    verdicts = {fp: verdict_of(e) for fp, e in judged.items()}
    votes: Dict[str, int] = {"real": 0, **{c: 0 for c in REASON_CATEGORIES}}
    for e in judged.values():
        for j in e["judges"]:
            votes["real" if j["verdict"] == "real" else j.get("reason_category") or "other"] += 1
    filed: Dict[str, int] = {}
    for _, f in occurrences:
        filed[f["category"]] = filed.get(f["category"], 0) + 1
    # one row per pull request the round covered, counting an occurrence under its own pull request
    per_pr = []
    for r in records:
        fps = [f["fingerprint"] for f in r["findings"]]
        j = [fp for fp in fps if fp in judged]
        real = [fp for fp in j if verdicts[fp] == "real"]
        per_pr.append({"pr": r["pr"], "title": r.get("title", ""), "files": len(r["files"]),
                       "findings": len(fps), "judged": len(j), "real": len(real),
                       "precision": (len(real) / len(j)) if j else None})
    real_total = sum(1 for v in verdicts.values() if v == "real")
    return {
        "records": len(records), "occurrences": len(occurrences), "distinct": len(fingerprints),
        "judged": len(judged), "real": real_total,
        "disputed": sum(1 for v in verdicts.values() if v == "disputed"),
        "not_real": sum(1 for v in verdicts.values() if v == "not_real"),
        "precision": (real_total / len(judged)) if judged else None,
        "unjudged": sorted(fp for fp in fingerprints if fp not in judged),
        "votes": votes, "filed": filed, "per_pr": per_pr, "fingerprints": fingerprints,
    }


def provenance(records: List[Dict[str, Any]], field: str) -> str:
    """The one value the round's records agree on for a field, over the records
    that carry one: a pull request whose review produced no finding has no model
    recorded against it, so reading records[0] named the harness's default
    instead of the round's model. Disagreement is a fact about the round, so it
    is printed and both values kept."""
    seen = sorted({str(r.get(field) or "") for r in records if r.get(field)})
    if len(seen) > 1:
        print(f"the records of this round disagree about {field}: {', '.join(seen)}", file=sys.stderr)
    return ", ".join(seen)


def partial_note(t: Dict[str, Any]) -> str:
    """How a round with unjudged findings says so wherever its number would
    otherwise be printed: the figure over part of a round is not the round's
    figure, and `score --markdown` is redirected straight into docs/."""
    return f"partial ({t['judged']} of {t['distinct']} judged)"


def score_text(tag: str, t: Dict[str, Any], records: List[Dict[str, Any]]) -> str:
    if t["unjudged"]:
        precision = partial_note(t)
    elif t["precision"] is not None:
        precision = f"{t['precision']:.2f} ({t['real']}/{t['judged']} judged)"
    else:
        precision = "not yet, nothing judged"
    out = [f"== precision, {tag} ==",
           f"findings      {t['occurrences']} occurrences over {t['records']} pull requests",
           f"distinct      {t['distinct']} fingerprints",
           f"judged        {t['judged']} of {t['distinct']}",
           f"real          {t['real']} (both judges)",
           f"not real      {t['not_real']}",
           f"disputed      {t['disputed']}",
           f"precision     {precision}"]
    out += ["", "votes, one per judge per finding (comparable with docs/REVIEW_QUALITY.md:27-35):"]
    for name, count in t["votes"].items():
        if count:
            out.append(f"  {name:<18} {count}")
    out += ["", "filed as:"] + [f"  {name:<18} {count}" for name, count in sorted(t["filed"].items())]
    out += ["", f"{'pr':>4} {'files':>5} {'find':>4} {'judged':>6} {'real':>4}  title"]
    for row in t["per_pr"]:
        out.append(f"{row['pr']:>4} {row['files']:>5} {row['findings']:>4} {row['judged']:>6} {row['real']:>4}  "
                   f"{_cell(row['title'])[:60]}")
    commits = sorted({r.get("pipeline_commit", "")[:12] for r in records if r.get("pipeline_commit")})
    cross = provenance(records, "cross_model")
    out += ["", f"pipeline {', '.join(commits) or 'unknown'}"
                + (" (dirty tree)" if any(r.get("pipeline_dirty") for r in records) else "")
                + f", model {provenance(records, 'model') or 'unknown'}"
                + (f" with {cross} cross-examining" if cross else "")
                + (", replayable" if all(r.get("replayable") for r in records) else ", not replayable")]
    return "\n".join(out) + "\n"


def score_markdown(tag: str, t: Dict[str, Any], records: List[Dict[str, Any]]) -> str:
    if t["unjudged"]:
        precision = partial_note(t)
    else:
        precision = f"{t['precision']:.2f}" if t["precision"] is not None else "n/a"
    # the file this is written to lives at docs/benchmarks/runs/<date>/, two levels under the protocol
    out = [f"# Precision, {tag}", "",
           f"`scripts/precision.py score` over {t['records']} pull request{'s' if t['records'] != 1 else ''} of the "
           "fixed set in `backend/tests/precision/pull_requests.json`, judged per finding in "
           "`backend/tests/precision/judgements.json`. The protocol is "
           "[../../PRECISION.md](../../PRECISION.md).", ""]
    if t["unjudged"]:
        out += [f"This round is partial: {t['judged']} of its {t['distinct']} distinct findings are judged, so the row "
                "below is not the round's number and must not be read as one.", ""]
    out += ["| Round | Findings | Distinct | Judged | Real | Disputed | Precision |",
            "| ----- | -------- | -------- | ------ | ---- | -------- | --------- |",
            f"| {tag} | {t['occurrences']} | {t['distinct']} | {t['judged']} | {t['real']} | {t['disputed']} | "
            f"{precision} |"]
    if any(t["votes"].values()):
        out += ["", "Why the rest were wrong, one vote per judge per finding:", "", "| Why | Votes |", "| --- | ----- |"]
        for name, count in t["votes"].items():
            if count:
                out.append(f"| {name.replace('_', ' ')} | {count} |")
    out += ["", "Per pull request:", "",
            "| PR | Files reviewed | Findings | Judged | Real | Precision |",
            "| -- | -------------- | -------- | ------ | ---- | --------- |"]
    for row in t["per_pr"]:
        p = f"{row['precision']:.2f}" if row["precision"] is not None else "n/a"
        out.append(f"| {row['pr']} | {row['files']} | {row['findings']} | {row['judged']} | {row['real']} | {p} |")
    commits = sorted({r.get("pipeline_commit", "")[:12] for r in records if r.get("pipeline_commit")})
    cross = provenance(records, "cross_model")
    out += ["", f"Model `{provenance(records, 'model') or 'unknown'}`"
                + (f", cross-examiner `{cross}`" if cross else "")
                + f", pipeline {', '.join(commits) or 'unknown'}. The raw records, with every model reply, are kept "
                  "outside the repository under `~/ReviewBot-runs/<date>/precision-runs/`."]
    return "\n".join(out) + "\n"


def cmd_score(args: argparse.Namespace) -> int:
    records = load_records(args.runs, args.tag)
    t = tally(records, load_ledger())
    sys.stdout.write(score_markdown(args.tag, t, records) if args.markdown else score_text(args.tag, t, records))
    if t["unjudged"]:
        print(f"{len(t['unjudged'])} finding{'s' if len(t['unjudged']) != 1 else ''} nobody has judged, so the number "
              f"above is over part of the round: {', '.join(t['unjudged'])}", file=sys.stderr)
        print(f"run: precision.py sheet {args.runs} {args.tag} --out <dir>", file=sys.stderr)
        return 2
    return 0


# ---------------------------------------------------------------- replay


async def cmd_replay(args: argparse.Namespace) -> int:
    records = load_records(args.runs, args.tag)
    unreplayable = [r["pr"] for r in records if not r.get("replayable")]
    if unreplayable:
        raise CannotRun(f"the records for pull requests {unreplayable} hold no model replies (replayable false), so "
                        f"there is nothing to push through the pipeline again; only a round produced by `run` can be "
                        f"replayed")
    verified = [r["pr"] for r in records if (r.get("settings") or {}).get("verify_findings")]
    if verified:
        raise CannotRun(f"the records for pull requests {verified} ran with VERIFY_FINDINGS on, and a verify reply sits "
                        f"between the reviewer's and the cross-examiner's in model_texts, so a replay would hand the "
                        f"cross-examiner the verify pass's words; such a round cannot be replayed")
    out = refuse_out_inside_repo(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ledger = load_ledger()
    before = tally(records, ledger)
    if before["unjudged"]:
        raise CannotRun(f"{len(before['unjudged'])} finding{'s' if len(before['unjudged']) != 1 else ''} of {args.tag} "
                        f"{'are' if len(before['unjudged']) != 1 else 'is'} unjudged, so there is no number before the "
                        f"change to compare with: {', '.join(before['unjudged'])}. Sheet and judge the round first")
    after_records: List[Dict[str, Any]] = []
    skipped_files = 0
    for record in records:
        settings = settings_for(record.get("model"), record.get("cross_model") or "",
                                record["settings"].get("max_files_per_review"),
                                record["settings"].get("min_finding_confidence"),
                                record["settings"].get("ollama_num_ctx"))
        files = [f for f in record["files"] if f.get("model_texts")]
        skipped_files += len(record["files"]) - len(files)
        texts = {f"{record['pr']}:{f['filename']}": f["model_texts"][0] for f in files}
        llm: Any = ReplayFileModel(model=record.get("model") or "replayed", texts=texts)
        recorder = Recorder()
        llm.callbacks = [recorder]
        cross_llm = None
        if record.get("cross_model"):
            cross_texts = {f"{record['pr']}:{f['filename']}": (f["model_texts"][1] if len(f["model_texts"]) > 1 else "")
                           for f in files}
            cross_llm = ReplayFileModel(model=record["cross_model"], texts=cross_texts)
            cross_llm.callbacks = [recorder]
        reviewer = FileReviewer(llm, settings, cross_llm=cross_llm)

        def key_for(filename: str, pr: int = record["pr"], one: Any = llm, two: Any = cross_llm) -> None:
            one.key = f"{pr}:{filename}"
            if two is not None:
                two.key = f"{pr}:{filename}"

        started = time.perf_counter()
        results, replies = await review_files([dict(f) for f in files], reviewer, recorder, settings, key_for=key_for)
        fresh = new_record({"number": record["pr"], "title": record.get("title", ""),
                            "base_sha": record["base_sha"], "head_sha": record["head_sha"]}, settings,
                           model=record.get("model") or "", cross_model=record.get("cross_model") or "")
        fresh["split"] = record.get("split", 0)
        fresh["skipped"] = list(record.get("skipped", []))
        fresh["replayed_from"] = {"tag": record["tag"], "runs": str(args.runs)}
        fill_record(fresh, [dict(f) for f in files], results, replies, settings.MIN_FINDING_CONFIDENCE)
        for f in record["files"]:
            if not f.get("model_texts"):
                # the model call raised on the night, so review_file returned before the recorder saw
                # anything (services/ai_reviewer.py:569-573); the file is carried, not re-reviewed
                fresh["errored"].append({"path": f["filename"],
                                         "reason": f.get("error") or "no model reply was recorded"})
        fresh["seconds"] = round(time.perf_counter() - started, 1)
        write_record(out, args.tag_out, record.get("repository", ""), fresh)
        after_records.append(fresh)
    after = tally(after_records, ledger)
    print(f"replayed {args.tag} as {args.tag_out} through the pipeline at "
          f"{(after_records[0].get('pipeline_commit') or 'unknown')[:12]}, no model loaded"
          + (f"; {skipped_files} file(s) recorded no reply and were carried, not re-reviewed" if skipped_files else ""))
    print(f"{'':<14}{'before':>8}{'after':>8}")
    for label, key in (("findings", "occurrences"), ("distinct", "distinct"), ("judged", "judged"), ("real", "real")):
        print(f"{label:<14}{before[key]:>8}{after[key]:>8}")
    print(f"{'precision':<14}{_ratio(before['precision']):>8}{_ratio(after['precision']):>8}")
    # the three sets are the round's provenance and nothing else: a fingerprint the change brought
    # out may already be in the ledger from another round, so what the number rests on is the
    # unjudged set, not the new one
    kept = sorted(set(before["fingerprints"]) & set(after["fingerprints"]))
    gone = sorted(set(before["fingerprints"]) - set(after["fingerprints"]))
    new = sorted(set(after["fingerprints"]) - set(before["fingerprints"]))
    print(f"carried {len(kept)} fingerprint(s), {len(gone)} vanished, {len(new)} new")
    known = judged_by(ledger)
    for fp in gone:
        e = known.get(fp)
        print(f"  gone    {fp} {verdict_of(e) if e else 'unjudged':<9} {e['path'] if e else ''}")
    rows = unjudged(after_records, ledger)
    if not rows:
        print("every finding after the change was already judged, so the number above is exact")
        return 0
    print(f"{len(rows)} finding{'s' if len(rows) != 1 else ''} nobody has judged; sheet "
          f"{'them' if len(rows) != 1 else 'it'} before the number is exact:")
    for _, f, prs in rows:
        print(f"  new     {f['fingerprint']} pr {', '.join(str(n) for n in prs)} {f['path']}:{f['line']} "
              f"{_cell(f['title'])[:70]}")
    best = (after["real"] + len(rows)) / (after["judged"] + len(rows))
    worst = after["real"] / (after["judged"] + len(rows))
    print(f"precision after is between {worst:.2f} and {best:.2f}, against {_ratio(before['precision'])} before")
    settled = before["precision"] is not None and (worst >= before["precision"] or best <= before["precision"])
    if settled:
        print("the bound settles it either way, so no judging is needed to read this replay")
        return 0
    print("the bound straddles the number before, so the unjudged findings have to be judged", file=sys.stderr)
    return 2


def _ratio(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.2f}"


# ---------------------------------------------------------------- the command line


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="precision.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = ap.add_subparsers(dest="command", required=True)

    run = subs.add_parser("run", help="review the fixed set and write one record per pull request")
    run.add_argument("--out", required=True, help="directory for the records; must be outside the repository")
    run.add_argument("--tag", default="run", help="name prefix for the records, one round per tag")
    run.add_argument("--model", default=None, help="the reviewer's Ollama tag; default OLLAMA_MODEL")
    run.add_argument("--cross-model", default=None, help="the cross-examiner's Ollama tag; default none")
    run.add_argument("--no-cross", action="store_true", help="the reviewer alone, whatever else says")
    run.add_argument("--unload", action="store_true",
                     help="ask Ollama to drop each model as the round finishes with it, for a machine that cannot "
                          "hold both")
    run.add_argument("--only", default="", help="comma-separated pull request numbers instead of all eleven")
    run.add_argument("--from-database", default=None,
                     help="build the round from the findings already stored in this reviews.db, with no model "
                          "(read-only and immutable); the record is marked unreplayable")
    run.add_argument("--max-files", type=int, default=None, help="MAX_FILES_PER_REVIEW for this round")
    run.add_argument("--min-confidence", type=float, default=None, help="MIN_FINDING_CONFIDENCE for this round")
    run.add_argument("--num-ctx", type=int, default=None, help="OLLAMA_NUM_CTX for this round")

    sheet = subs.add_parser("sheet", help="the unjudged findings as a judge's sheet and a skeleton to fill")
    sheet.add_argument("runs")
    sheet.add_argument("tag")
    sheet.add_argument("--out", default=None, help="write <tag>-sheet.md and <tag>-skeleton.json here")
    sheet.add_argument("--context", type=int, default=6, help="lines of the file either side of a finding")

    merge = subs.add_parser("merge", help="fold two judges' filled skeletons into the ledger")
    merge.add_argument("filled", nargs="+", help="the filled skeletons, one per judge")
    merge.add_argument("--skip-existing", action="store_true",
                       help="a fingerprint the ledger already holds gains this pull request instead of being refused")

    score = subs.add_parser("score", help="the round's number, its reason breakdown and its per-pull-request table")
    score.add_argument("runs")
    score.add_argument("tag")
    score.add_argument("--markdown", action="store_true", help="the round's row for docs/benchmarks/runs/<date>/")

    replay = subs.add_parser("replay", help="a recorded round through the current pipeline, with no model")
    replay.add_argument("runs")
    replay.add_argument("tag")
    replay.add_argument("--out", required=True, help="directory for the new records; outside the repository")
    replay.add_argument("--tag-out", required=True, help="the tag the replayed round is written under")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    for noisy in ("httpx", "httpcore", "services.ai_reviewer", "services.review_workflow"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        if args.command == "run":
            return asyncio.run(cmd_run(args))
        if args.command == "sheet":
            return cmd_sheet(args)
        if args.command == "merge":
            return cmd_merge(args)
        if args.command == "score":
            return cmd_score(args)
        return asyncio.run(cmd_replay(args))
    except CannotRun as e:
        print(f"precision: {e}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as e:
        # a record, a skeleton or the ledger that cannot be opened or is not JSON is an ordinary
        # mistake at the command line, and a traceback says less about it than one line does
        print(f"precision: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
