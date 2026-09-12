#!/usr/bin/env python
"""Review a diff with no network: a branch range, a .diff file or stdin, through
the same pipeline the GitHub App runs, printed instead of posted.

Usage, from backend/ with the venv and Ollama serving on loopback:
    .venv/bin/python scripts/review_diff.py                          # main...HEAD of the current repository
    .venv/bin/python scripts/review_diff.py --range v1.1.0..v1.2.0
    .venv/bin/python scripts/review_diff.py --repo ~/src/other --range main...feature --no-cross
    .venv/bin/python scripts/review_diff.py --staged --format markdown
    .venv/bin/python scripts/review_diff.py --file change.diff --format json    # git diff output, not any unified diff
    git diff main...HEAD | .venv/bin/python scripts/review_diff.py --file -

What runs is what the App runs on a pull request: the same file selection and
size gate, the same redaction, the same reviewer, cross-examiner and verify
pass, the same post-filters, the same renderer for --format markdown. Model
settings are read from backend/.env so a local review matches the App, and a
flag given here overrides only that one setting. No GitHub credentials are
needed or read, nothing is written to the database, and STRICT_LOCAL is pinned
on, so a cloud model tag is refused however it is configured. The only peer
the process ever dials is Ollama on loopback, which is the point: with the
wifi off this command still reviews a branch.

Exit codes: 0 reviewed, 1 reviewed but a file's model call failed, 2 could not run."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# Nothing here reads a cloud key or a tracing flag, and STRICT_LOCAL is pinned on below. The names
# are popped from this process, as the harness does, so the local-only guard judges the command
# rather than the shell it was started from, and so that LangChain cannot find a tracing flag at
# call time: with the variables gone there is nothing in this process that could post a prompt.
# The proxy variables go too: httpx honours them by default, and a shell proxy would carry every
# model call, redacted diff included, to the proxy host instead of to Ollama on loopback.
POPPED_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY", "LANGCHAIN_API_KEY",
               "LANGSMITH_API_KEY", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING", "LANGSMITH_TRACING_V2",
               "LANGCHAIN_TRACING", "LANGCHAIN_HANDLER", "SENTRY_DSN",
               "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
for _var in POPPED_VARS:
    os.environ.pop(_var, None)
# config.settings builds a module-level Settings on import and insists on the App's three GitHub
# secrets; the command never uses them, so placeholders stand in (a private key that really
# parses, because the validator signs with it). The command's own Settings is built in build_settings.
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

_PLACEHOLDER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
_PLACEHOLDERS = {"GITHUB_APP_ID": "1", "GITHUB_PRIVATE_KEY": _PLACEHOLDER_KEY,
                 "GITHUB_WEBHOOK_SECRET": "review-diff-not-a-secret-0123456789",
                 "LOCAL_API_TOKEN": "", "DATABASE_URL": "sqlite:///:memory:"}
for _key, _value in _PLACEHOLDERS.items():
    os.environ.setdefault(_key, _value)

import logging  # noqa: E402

try:
    from config.settings import LocalOnlyViolation, Settings  # noqa: E402
except (RuntimeError, ValueError) as _refused:  # the module-level Settings the App builds on import refused the environment
    print(f"review_diff: could not load the App's settings: {_refused}", file=sys.stderr)
    sys.exit(2)
from services.ai_reviewer import FileReviewer, FileReviewResult  # noqa: E402
from services.comment_renderer import render_review  # noqa: E402
from services.git_diff import GITHUB_CONTEXT_LINES, file_at, split_git_diff  # noqa: E402
from services.llm import build_chat_model, build_cross_model, ollama_health, unload_model  # noqa: E402
from services.prompts import review_prompt_with_context  # noqa: E402
from services.review_runner import prepare_files, select_files  # noqa: E402
from services.review_workflow import ReviewWorkflow  # noqa: E402

FORMATS = ("text", "markdown", "json")
_DROPPED_CATEGORIES = {"Cc", "Cf", "Zl", "Zp"}  # an escape sequence in a model reply must not reach a terminal


class CannotRun(Exception):
    """A reason the review cannot start; printed to stderr, exit code 2."""


def diff_argv(repo: str, range_spec: Optional[str], staged: bool = False) -> List[str]:
    """The one git command the script runs. The user's diff configuration is
    overridden so the text is what the splitter expects: a/ and b/ prefixes,
    three lines of context like GitHub, renames detected, no colour, no
    external diff or textconv. A range that begins with a dash is refused
    before git sees it, so it cannot be read as an option."""
    for value in (repo, range_spec or ""):
        if value.startswith("-"):
            raise CannotRun(f"refusing {value!r}: it begins with a dash")
    argv = ["git", "--no-pager", "-C", repo,
            "-c", "core.quotepath=false", "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false",
            "-c", "diff.relative=false", "-c", "diff.renames=true",
            "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--find-renames",
            f"--unified={GITHUB_CONTEXT_LINES}", "--src-prefix=a/", "--dst-prefix=b/"]
    if staged:
        argv.append("--cached")
    if range_spec:
        argv.append(range_spec)
    argv.append("--")
    return argv


def run_git_diff(repo: str, range_spec: Optional[str], staged: bool) -> str:
    argv = diff_argv(repo, range_spec, staged)
    try:
        done = subprocess.run(argv, capture_output=True, check=False)
    except FileNotFoundError:
        raise CannotRun("git is not on PATH")
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", errors="replace").strip()
        hint = " (name the range with --range, or --repo the repository)" if "unknown revision" in detail or "bad revision" in detail else ""
        raise CannotRun(f"git diff failed: {detail}{hint}")
    return done.stdout.decode("utf-8", errors="replace")


def new_side(args: argparse.Namespace) -> Optional[str]:
    """What the new side of this diff is, as git names it: a revision for a
    range, "" for the index (`--staged` diffs the index, not the tree), and None
    for the files on disk, which only `--range <one revision>` compares against.
    A diff read from a file or stdin names no side at all, so it gets no file
    context: a file from this working tree need not be the file that diff was
    taken from.

    A range's new side is whatever follows the last pair of dots, `HEAD`
    included: `main...HEAD` diffs the commit, so reading the working tree there
    would show the model lines no diff in the run mentions."""
    if args.file is not None:
        return None
    if args.staged:
        return ""
    spec = args.range or "main...HEAD"
    if ".." not in spec:
        return None   # `--range main` compares a commit with the files on disk, so read those
    right = (spec.split("...")[-1] if "..." in spec else spec.split("..")[-1]).strip()
    return right or "HEAD"


def resolve_rev(repo: str, rev: str) -> str:
    """The commit a range's right-hand side names, through `git rev-parse`, or ""
    when git cannot resolve it: a branch, a tag or `HEAD` is read at the commit
    it points at, so the listing is the file the diff's new side holds."""
    if rev.startswith("-"):
        return ""
    try:
        done = subprocess.run(["git", "--no-pager", "-C", repo, "rev-parse", "--verify", f"{rev}^{{commit}}"],
                              capture_output=True, check=False)
    except (FileNotFoundError, OSError):
        return ""
    return done.stdout.decode("utf-8", errors="replace").strip() if done.returncode == 0 else ""


def where_read(args: argparse.Namespace) -> str:
    """How the progress line names the side the files were read from."""
    side = new_side(args)
    return "the working tree" if side is None else (side or "the index")


def file_texts(args: argparse.Namespace, files: List[Dict[str, Any]]) -> int:
    """Hang the file the hunk came from on each prepared file, the way the App's
    contents call does, and return how many were read. Only when FILE_CONTEXT is
    on, and never for a diff read from a file or stdin. The side the diff was
    taken against is the side the file is read from, or the model would be shown
    a file the diff does not describe: a range at its resolved commit, a staged
    change at the index, and only a dotless `--range` off the disk."""
    if args.file is not None:
        return 0
    repo = str(Path(args.repo).resolve())
    side = new_side(args)
    rev = resolve_rev(repo, side) if side else side
    read = 0
    for f in files:
        if f.get("status") == "added":
            continue   # the diff of an added file is already the whole file
        if side is None:
            path = Path(repo, f["filename"])
            try:
                text = path.read_text(encoding="utf-8") if path.is_file() else ""
            except (OSError, UnicodeDecodeError):
                text = ""
        elif side and not rev:
            text = ""   # the right-hand side did not resolve; reading the wrong file is worse than none
        else:
            text = file_at(repo, rev, f["filename"])
        if text:
            f["file_text"] = text
            read += 1
    return read


def read_diff(args: argparse.Namespace) -> Tuple[str, str]:
    """The diff text and a label for it."""
    if args.file is not None:
        if args.file == "-":
            return sys.stdin.buffer.read().decode("utf-8", errors="replace"), "stdin"
        if not args.file:
            raise CannotRun("--file needs a path, or - for stdin")
        path = Path(args.file)
        if not path.is_file():
            raise CannotRun(f"{args.file} is not a file")
        return path.read_text(encoding="utf-8", errors="replace"), path.name
    repo = str(Path(args.repo).resolve())
    if not Path(repo).is_dir():
        raise CannotRun(f"{args.repo} is not a directory")
    if args.staged:
        return run_git_diff(repo, None, staged=True), "staged changes"
    range_spec = args.range or "main...HEAD"
    return run_git_diff(repo, range_spec, staged=False), range_spec


def build_settings(args: argparse.Namespace) -> Settings:
    """The App's settings from backend/.env, with the GitHub secrets and the
    database replaced by placeholders, STRICT_LOCAL pinned on, and only the
    flags the user gave laid over the top. An init value outranks the env
    file, so a flag left at None never overwrites a setting from .env."""
    overrides: Dict[str, Any] = dict(_PLACEHOLDERS)
    overrides["STRICT_LOCAL"] = "true"
    if args.model is not None:
        overrides["OLLAMA_MODEL"] = args.model
    if args.no_cross:
        overrides["CROSS_EXAMINE_MODEL"] = ""
    elif args.cross_model is not None:
        overrides["CROSS_EXAMINE_MODEL"] = args.cross_model
    if args.verify is not None:
        overrides["VERIFY_FINDINGS"] = "true" if args.verify else "false"
    if args.max_files is not None:
        overrides["MAX_FILES_PER_REVIEW"] = args.max_files
    env_file: Optional[str]
    if args.env_file is None:
        env_file = str(BACKEND / ".env")
        if not Path(env_file).is_file():
            env_file = None  # no backend/.env yet: the defaults, as the App would have
    elif args.env_file:
        env_file = args.env_file
        if not Path(env_file).is_file():
            raise CannotRun(f"--env-file {args.env_file} is not a file")
    else:
        env_file = None
    if args.max_files is not None and args.max_files < 1:
        raise CannotRun("--max-files must be at least 1")
    try:
        return Settings(_env_file=env_file, **overrides)
    except LocalOnlyViolation as e:
        raise CannotRun(f"refused by the local-only guard: {e}")
    except ValueError as e:
        raise CannotRun(f"settings are invalid: {e}")


def _plain(text: str) -> str:
    return "".join(ch for ch in (text or "") if ch in "\n\t" or unicodedata.category(ch) not in _DROPPED_CATEGORIES)


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in _plain(text).splitlines()) or prefix


def render_text(label: str, results: Sequence[FileReviewResult], skipped: Sequence[Tuple[str, str]],
                totals: Dict[str, int], settings: Settings, redaction_total: int, files_errored: int = 0) -> str:
    """The review as plain text for a terminal: every finding with its evidence,
    its recommendation and its provenance, then the files not reviewed, then the
    counts. results holds the usable file reviews only; a file the model did not
    come back usable for is in skipped with its reason, as the App lists it."""
    out: List[str] = []
    findings_total = sum(len(r.review.findings) for r in results)
    out.append(f"ReviewBot review of {_plain(label)}: {findings_total} finding{'s' if findings_total != 1 else ''} "
               f"in {len(results)} file{'s' if len(results) != 1 else ''} reviewed"
               + (f", {len(skipped)} not reviewed" if skipped else ""))
    if files_errored:
        out.append(f"The model did not return a usable review for {files_errored} file{'s' if files_errored != 1 else ''}; "
                   "they are listed under Not reviewed.")
    cross = settings.CROSS_EXAMINE_MODEL
    for r in results:
        if not r.review.findings:
            continue
        for f in r.review.findings:
            out.append("")
            out.append(f"{_plain(r.filename)}:{f.line}  {f.severity.value} {f.category.value}  {_plain(f.title)}")
            if f.evidence:
                out.append(_indent(f.evidence, "    evidence: "))
            if f.recommendation:
                out.append(_indent(f.recommendation, "    "))
            source = getattr(f, "source_model", "")
            if cross and source == cross:
                out.append(f"    found by the cross-examiner ({_plain(cross)})")
            elif getattr(f, "cross_verdict", None) == "false_positive":
                out.append(f"    the cross-examiner disagreed: {_plain(getattr(f, 'cross_reason', '') or 'no reason given')}")
    summaries = [r for r in results if r.review.summary]
    if summaries:
        out.append("")
        out.append("Per file:")
        for r in summaries:
            out.append(f"  {_plain(r.filename)}: {_plain(r.review.summary)}")
    if skipped:
        out.append("")
        out.append("Not reviewed:")
        for name, reason in skipped:
            out.append(f"  {_plain(name)}: {_plain(reason)}")
    counts: Dict[str, int] = {}
    for r in results:
        for f in r.review.findings:
            counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
    by_severity = ", ".join(f"{sev} {counts[sev]}" for sev in ("critical", "high", "medium", "low", "info") if sev in counts) or "none"
    out.append("")
    out.append(f"Findings by severity: {by_severity}. Dropped by the post-filters: {totals.get('dropped', 0)}."
               + (f" Redacted before the model saw it: {redaction_total}." if redaction_total else ""))
    models = f"Reviewed by {settings.OLLAMA_MODEL}" + (f", cross-examined by {cross}" if cross else "") + " on loopback Ollama"
    seconds = sum(r.duration_seconds for r in results)
    out.append(f"{models}; {totals.get('prompt_tokens', 0)} prompt tokens, {totals.get('output_tokens', 0)} output tokens, "
               f"{seconds:.0f} seconds"
               + (f"; the cross-examiner added {totals.get('cross_added', 0)} and refuted {totals.get('cross_refuted', 0)}" if cross else "")
               + ".")
    return "\n".join(out) + "\n"


def render_markdown(results: Sequence[FileReviewResult], skipped: Sequence[Tuple[str, str]], totals: Dict[str, int],
                    settings: Settings, redaction_total: int, files_errored: int = 0) -> str:
    """Exactly what the App would post: the summary comment, then the inline
    comment bodies under the path and line they would attach to."""
    rendered = render_review(results, model=settings.OLLAMA_MODEL, skipped=skipped, redaction_total=redaction_total,
                             files_errored=files_errored,
                             cross_model=settings.CROSS_EXAMINE_MODEL or None,
                             cross_added=totals.get("cross_added", 0), cross_refuted=totals.get("cross_refuted", 0),
                             max_inline=settings.MAX_INLINE_COMMENTS)
    parts = [rendered.body.rstrip("\n")]
    for c in rendered.comments:
        parts.append(f"\n### `{c['path']}` line {c['line']}\n\n{c['body']}")
    return _plain("\n".join(parts)) + "\n"


def render_json(label: str, results: Sequence[FileReviewResult], skipped: Sequence[Tuple[str, str]],
                totals: Dict[str, int], settings: Settings, redaction_total: int) -> str:
    files = []
    for r in results:
        files.append({
            "filename": r.filename, "language": r.language, "status": r.status, "error": r.error, "parse_ok": r.parse_ok,
            "summary": r.review.summary, "findings": [f.model_dump(mode="json") for f in r.review.findings],
            "dropped": r.dropped, "prompt_tokens": r.prompt_tokens, "output_tokens": r.output_tokens,
            "seconds": round(r.duration_seconds, 1), "cross_calls": r.cross_calls,
            "cross_refuted": r.cross_refuted, "cross_added": r.cross_added, "refuted": r.refuted,
        })
    doc = {"source": label, "model": settings.OLLAMA_MODEL, "cross_model": settings.CROSS_EXAMINE_MODEL or None,
           "files": files, "skipped": [[name, reason] for name, reason in skipped], "totals": totals,
           "redactions": redaction_total}
    return json.dumps(doc, indent=1) + "\n"


async def review(args: argparse.Namespace, settings: Settings, text: str, label: str) -> Tuple[str, int]:
    """Run the pipeline over the diff text and return the rendered review and the exit code."""
    raw_files = split_git_diff(text)
    if not raw_files:
        if text.strip():
            raise CannotRun("no `diff --git` section found: --file expects the output of git diff, git show or git format-patch")
        return "Nothing to review: the diff is empty.\n", 0
    combined = [f["filename"] for f in raw_files if f["status"] == "combined"]
    if combined:
        raise CannotRun("a combined diff of a merge commit cannot be reviewed (" + ", ".join(combined[:3])
                        + "); diff the merge against one parent instead, for example --range <merge>^1..<merge>")
    selected, skipped = select_files(raw_files, settings)
    files, redaction_total = prepare_files(selected)
    if files and settings.FILE_CONTEXT:
        read = file_texts(args, files)
        if not args.quiet:
            print(f"file context on: {read} of {len(files)} files read at {where_read(args)}",
                  file=sys.stderr, flush=True)
    if not files:
        lines = ["Nothing to review: no eligible file in the diff.", "Not reviewed:"]
        lines += [f"  {_plain(name)}: {_plain(reason)}" for name, reason in skipped]
        return "\n".join(lines) + "\n", 0
    health = await ollama_health(settings)
    if not health.get("reachable") or not health.get("model_present"):
        raise CannotRun(f"Ollama at {settings.OLLAMA_BASE_URL} is not reachable or {settings.OLLAMA_MODEL} is not pulled "
                        f"(ollama pull {settings.OLLAMA_MODEL}): {health}")
    if settings.CROSS_EXAMINE_MODEL and not health.get("cross_model_present"):
        raise CannotRun(f"the cross-examiner {settings.CROSS_EXAMINE_MODEL} is not pulled "
                        f"(ollama pull {settings.CROSS_EXAMINE_MODEL}, or --no-cross)")
    llm = build_chat_model(settings)
    cross_llm = build_cross_model(settings)
    # the same prompt production uses with the switch on, or the block would never be rendered
    reviewer = FileReviewer(llm, settings, cross_llm=cross_llm,
                            **({"prompt": review_prompt_with_context} if settings.FILE_CONTEXT else {}))
    quiet = args.quiet

    async def on_progress(phase: str, done: int, total: int, current: str) -> None:
        if current and not quiet:
            print(f"[{done + 1}/{total}] {phase} {_plain(current)}", file=sys.stderr, flush=True)

    async def unload(model: str) -> bool:
        if not quiet:
            print(f"unloading {_plain(model)}", file=sys.stderr, flush=True)
        return await unload_model(settings, model)

    workflow = ReviewWorkflow(reviewer, unload=unload, on_progress=on_progress)
    state = await workflow.run(Path(args.repo).resolve().name if not args.file else "local", 0, label, files)
    results: List[FileReviewResult] = list(state.get("results", []))
    totals: Dict[str, int] = dict(state.get("totals", {}))
    # The runner's own split (services/review_runner.py): a file whose model call failed or whose reply
    # could not be read is listed under Not reviewed with the reason, and only usable results are rendered.
    succeeded = [r for r in results if r.parse_ok and not r.error]
    errored = [r for r in results if not (r.parse_ok and not r.error)]
    skipped = list(skipped) + [(r.filename, f"the model did not return a usable review ({r.error or 'unreadable reply'})")
                               for r in errored]
    if args.format == "markdown":
        rendered = render_markdown(succeeded, skipped, totals, settings, redaction_total, files_errored=len(errored))
    elif args.format == "json":
        rendered = render_json(label, results, skipped, totals, settings, redaction_total)
    else:
        rendered = render_text(label, succeeded, skipped, totals, settings, redaction_total, files_errored=len(errored))
    return rendered, (1 if errored else 0)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = ap.add_mutually_exclusive_group()
    source.add_argument("--range", default=None, help="a git revision range, A..B or A...B; default main...HEAD, the pull request form")
    source.add_argument("--staged", action="store_true", help="the staged changes of the repository instead of a range")
    source.add_argument("--file", default=None, help="a file holding git diff output, or - for stdin")
    ap.add_argument("--repo", default=".", help="the repository to diff (default: the current directory)")
    ap.add_argument("--model", default=None, help="the reviewer's Ollama tag; default OLLAMA_MODEL from backend/.env")
    ap.add_argument("--cross-model", default=None, help="the cross-examiner's Ollama tag; default CROSS_EXAMINE_MODEL from backend/.env")
    ap.add_argument("--no-cross", action="store_true", help="review with the reviewer alone whatever backend/.env says")
    ap.add_argument("--verify", action=argparse.BooleanOptionalAction, default=None,
                    help="run the verify pass on every finding (--no-verify switches it off); default VERIFY_FINDINGS")
    ap.add_argument("--max-files", type=int, default=None, help="at most this many files, riskiest first; default MAX_FILES_PER_REVIEW")
    ap.add_argument("--format", choices=FORMATS, default="text", help="text for a terminal, markdown as the App would post it, json")
    ap.add_argument("--env-file", default=None, help="settings file to read instead of backend/.env; '' reads none")
    ap.add_argument("--quiet", action="store_true", help="no progress lines on stderr")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    for noisy in ("httpx", "httpcore", "services.ai_reviewer", "services.review_workflow"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        settings = build_settings(args)
        text, label = read_diff(args)
        rendered, code = asyncio.run(review(args, settings, text, label))
    except CannotRun as e:
        print(f"review_diff: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(rendered)
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
