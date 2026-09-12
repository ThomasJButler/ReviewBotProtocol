#!/usr/bin/env python
"""What the file context costs, and the case files a measured round needs. No
model, no network.

Usage, from backend/ with the venv:
    .venv/bin/python scripts/file_context_budget.py --range v1.1.0..v1.2.0 --ctx 16384,32768
    .venv/bin/python scripts/file_context_budget.py --range main...HEAD
    .venv/bin/python scripts/file_context_budget.py --emit-cases ~/runs/realpr.json --range main...HEAD
    .venv/bin/python scripts/file_context_budget.py --emit-corpus-cases ~/runs/corpus.json
    .venv/bin/python scripts/file_context_budget.py --emit-corpus-cases ~/runs/corpus-padded.json --pad --redteam

--range walks one git range, splits it with services/git_diff.py, reads each
file at the range's head, and prints the patch bytes, the file bytes and the
mode services/file_context.py would choose at each context size, then the mode
distribution against patch size. That distribution is the honest version of the
roadmap's cost metric: the size gate looks at the patch alone, so turning file
context on can never change which files are skipped, and what it does instead is
leave the largest patches with no context at all.

--emit-corpus-cases writes the committed corpus as the bare JSON list of case
dicts that scripts/prompt_overhead.py and prompt_eval's --cases-from-file read,
which nothing else emits. --pad also synthesises a file around each hunk from
the hunk header's own offsets, padded with whole bodies of the corpus's clean
cases of the same language, so the padding holds nothing to report. It is
synthesised code and not real code, and only the +filectx variant of a round is
shown it, so the two variants of a padded round do not read the same file and a
finding filed on the padding is a false positive by construction. A case that
already carries its own file text keeps it."""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# The bootstrap scripts/prompt_eval.py uses: the App's three secrets are placeholders because
# config.settings builds a Settings at import time, and nothing here reads a credential.
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

_THROWAWAY_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
_PLACEHOLDERS = {"GITHUB_APP_ID": "1", "GITHUB_PRIVATE_KEY": _THROWAWAY_KEY,
                 "GITHUB_WEBHOOK_SECRET": "file-context-budget-not-a-secret-0123456789",
                 "LOCAL_API_TOKEN": "", "DATABASE_URL": "sqlite:///:memory:"}
for _key, _value in _PLACEHOLDERS.items():
    os.environ.setdefault(_key, _value)

from config.settings import Settings  # noqa: E402
from services import file_context  # noqa: E402
from services.diff import hunk_spans, parse_patch  # noqa: E402
from services.git_diff import GITHUB_CONTEXT_LINES, file_at, split_git_diff  # noqa: E402
from services.review_runner import select_files  # noqa: E402
from tests.prompt_corpus import CASES  # noqa: E402
from tests.prompt_redteam import REDTEAM_CASES  # noqa: E402

MARKER = "<<<DIFF_DATA_FILE_budget>>>"  # a stand-in for the per-request nonce label; only its length matters here
PATCH_BUCKETS = ((2_000, "under 2 KB"), (8_000, "2 to 8 KB"), (16_000, "8 to 16 KB"), (32_000, "16 to 32 KB"))


class CannotRun(Exception):
    """A reason the command cannot start; printed to stderr, exit code 2."""


def git_diff(repo: str, range_spec: str) -> str:
    """The same git invocation scripts/review_diff.py uses, so the text this
    measures is the text the offline reviewer would read."""
    for value in (repo, range_spec):
        if value.startswith("-"):
            raise CannotRun(f"refusing {value!r}: it begins with a dash")
    argv = ["git", "--no-pager", "-C", repo,
            "-c", "core.quotepath=false", "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false",
            "-c", "diff.relative=false", "-c", "diff.renames=true",
            "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--find-renames",
            f"--unified={GITHUB_CONTEXT_LINES}", "--src-prefix=a/", "--dst-prefix=b/", range_spec, "--"]
    try:
        done = subprocess.run(argv, capture_output=True, check=False)
    except FileNotFoundError:
        raise CannotRun("git is not on PATH")
    if done.returncode != 0:
        raise CannotRun(f"git diff failed: {done.stderr.decode('utf-8', errors='replace').strip()}")
    return done.stdout.decode("utf-8", errors="replace")


def head_of(range_spec: str) -> str:
    """The revision the new side of this diff is, or "" for the working tree: a
    range with no dots in it (`git diff main`) compares a commit with the files
    on disk, so reading those files at that commit would price the old side."""
    if ".." not in range_spec:
        return ""
    return (range_spec.split("...")[-1] if "..." in range_spec else range_spec.split("..")[-1]).strip() or "HEAD"


def settings_at(num_ctx: int) -> Settings:
    return Settings(_env_file=None, **_PLACEHOLDERS).model_copy(update={"OLLAMA_NUM_CTX": num_ctx, "FILE_CONTEXT": True})


def bucket(patch_bytes: int) -> str:
    for limit, label in PATCH_BUCKETS:
        if patch_bytes < limit:
            return label
    return "over 32 KB"


def read_file(repo: str, rev: str, path: str) -> str:
    """The file as the new side of the diff has it: at the revision when the
    range names one, from the working tree when it does not."""
    if rev:
        return file_at(repo, rev, path)
    on_disk = Path(repo, path)
    try:
        return on_disk.read_text(encoding="utf-8") if on_disk.is_file() else ""
    except (OSError, UnicodeDecodeError):
        return ""


def measure(files: List[Dict[str, Any]], repo: str, rev: str, sizes: List[int]) -> List[Dict[str, Any]]:
    """One row per file: its patch, its whole text at the head, and what render
    would do with the two of them at each context size."""
    rows: List[Dict[str, Any]] = []
    for f in files:
        patch = str(f.get("patch") or "")
        text = "" if f.get("status") == "added" else read_file(repo, rev, str(f["filename"]))
        row: Dict[str, Any] = {
            "filename": f["filename"], "status": f.get("status", "modified"), "skip": f.get("skip", ""),
            "patch_bytes": len(patch.encode("utf-8")), "file_bytes": len(text.encode("utf-8")),
            "file_lines": len(text.splitlines()), "modes": {}, "rendered": {},
        }
        for size in sizes:
            rendered = file_context.render(text, patch, settings_at(size), MARKER)
            row["modes"][size] = rendered.mode
            row["rendered"][size] = len(rendered.block.encode("utf-8"))
        rows.append(row)
    return rows


def print_table(rows: List[Dict[str, Any]], sizes: List[int]) -> None:
    print("status A is a file this range added: its diff is already the whole file, so it is sent no listing")
    head = f"{'file':<48} {'st':>2} {'patch':>8} {'file':>8} {'lines':>6}"
    for size in sizes:
        head += f" {'mode@' + str(size // 1024) + 'k':>12} {'bytes':>8}"
    print(head)
    for r in rows:
        line = (f"{str(r['filename'])[:48]:<48} {str(r['status'])[:1].upper():>2} {r['patch_bytes']:>8} "
                f"{r['file_bytes']:>8} {r['file_lines']:>6}")
        for size in sizes:
            line += f" {r['modes'][size]:>12} {r['rendered'][size]:>8}"
        print(line + (f"   (not reviewed: {r['skip']})" if r["skip"] else ""))


def print_summary(rows: List[Dict[str, Any]], sizes: List[int]) -> None:
    reviewed = [r for r in rows if not r["skip"]]
    print(f"\n== modes over the {len(reviewed)} files a review would read ==")
    for size in sizes:
        counts = {mode: sum(1 for r in reviewed if r["modes"][size] == mode) for mode in ("whole", "window", "none")}
        added = sum(1 for r in reviewed if r["status"] == "added")
        budget = file_context.budget_bytes(settings_at(size))
        print(f"  num_ctx {size:>6} (budget {budget} bytes): whole {counts['whole']}, "
              f"window {counts['window']}, none {counts['none']} ({added} of them files this range added)")
    labels = [label for _, label in PATCH_BUCKETS] + ["over 32 KB"]
    print("\n== mode by patch size ==")
    print(f"{'patch size':<14} {'files':>6}" + "".join(f" {'whole/window/none @' + str(s // 1024) + 'k':>26}" for s in sizes))
    for label in labels:
        group = [r for r in reviewed if bucket(r["patch_bytes"]) == label]
        if not group:
            continue
        line = f"{label:<14} {len(group):>6}"
        for size in sizes:
            counts = [sum(1 for r in group if r["modes"][size] == mode) for mode in ("whole", "window", "none")]
            line += f" {'/'.join(str(c) for c in counts):>26}"
        print(line)


def hunks_only(patch: str) -> str:
    """Everything from the first hunk header on. A case file must hold GitHub's
    shape, not git's: services/diff.py never resets its in_hunk flag, so a
    `+++ b/name` line would be counted as an added line."""
    lines = patch.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("@@ "):
            return "\n".join(lines[i:])
    return ""


def case_dicts(pad: bool, redteam: bool) -> Tuple[List[Dict[str, Any]], List[str]]:
    """The committed cases as plain dicts, and the keys nothing could pad."""
    cases = list(CASES) + (list(REDTEAM_CASES) if redteam else [])
    out = [asdict(c) for c in cases]
    unpadded: List[str] = []
    if not pad:
        return out, unpadded
    bodies = clean_bodies()
    for d in out:
        if d.get("file_text"):
            continue   # a case that carries its own file, such as a file-borne injection, keeps it
        for_language = bodies.get(d["language"])
        if not for_language:
            unpadded.append(d["key"])
            continue
        d["file_text"] = synthesise(d["patch"], for_language)
    return out, unpadded


def clean_bodies() -> Dict[str, List[List[str]]]:
    """Padding, per language, as the whole body of each clean case: code the
    corpus already says holds nothing to report, so padding a file cannot plant a
    second bug, and kept in one piece so what surrounds a hunk reads as code
    rather than as lines of several files interleaved."""
    out: Dict[str, List[List[str]]] = {}
    for case in CASES:
        if not case.clean:
            continue
        body = [line[1:] if line[:1] in (" ", "+") else line
                for line in hunks_only(case.patch).split("\n")[1:] if line[:1] in (" ", "+")]
        while body and not body[-1].strip():
            body.pop()
        if body:
            out.setdefault(case.language, []).append(body)
    return out


_DEFINITION = re.compile(r"^\s*(?:def|class|function|interface|type|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)")


def _renamed(body: List[str], suffix: int) -> List[str]:
    """The same body with every name it defines given a suffix, so a body used
    twice does not define one name twice."""
    out = list(body)
    for line in body:
        m = _DEFINITION.match(line)
        if m:
            name = m.group(1)
            out = [re.sub(rf"\b{re.escape(name)}\b", f"{name}_{suffix}", l) for l in out]
    return out


def synthesise(patch: str, bodies: List[List[str]], min_lines: int = 150, factor: int = 6) -> str:
    """A file around the hunks, built from the hunk headers' own offsets: the
    new-side lines of each hunk sit exactly where the header says they do, the
    gaps before, between and after them are padding, and the file is long enough
    that the hunk is a small part of it, which is the point of the padded round.

    The padding is whole clean-case bodies, one after another with a blank line
    between them and a suffix on the names when a body is used twice, rather than
    fragments of several cases interleaved. It is synthesised code all the same:
    the hunk is written over whatever padding sits at its numbers, so the body it
    lands in is left part-written, and the file has to read as the file the hunk
    came from rather than compile. It is asymmetric too, since only the +filectx
    variant of a round is shown it."""
    spans = hunk_spans(patch)
    parsed = parse_patch(patch)
    if not spans or not bodies:
        return ""
    last = max(end for _, end in spans)
    total = max(min_lines, factor * len(parsed.new_lines), last + 40)
    lines: List[str] = []
    used = 0
    while len(lines) < total:
        body = bodies[used % len(bodies)]
        repeat = used // len(bodies)
        lines.extend(_renamed(body, repeat) if repeat else body)
        lines.append("")
        used += 1
    lines = lines[:total]
    for number, text in parsed.new_lines.items():
        if 1 <= number <= total:
            lines[number - 1] = text
    return "\n".join(lines) + "\n"


def emit_cases_from_range(path: str, rows: List[Dict[str, Any]], repo: str, rev: str,
                          files: List[Dict[str, Any]]) -> int:
    """The reviewed files of a range as a case file: real code, so recall and
    false positives mean nothing on these rows and only the cost, the modes and
    the raw replies are worth reading."""
    by_name = {str(f["filename"]): f for f in files}
    cases = []
    for r in rows:
        if r["skip"]:
            continue
        f = by_name[str(r["filename"])]
        patch = hunks_only(str(f.get("patch") or ""))
        if not patch:
            continue
        cases.append({
            "key": str(r["filename"]).replace("/", "_").replace(".", "_")[:60],
            "filename": str(r["filename"]), "language": f.get("language", "unknown") or "unknown",
            "patch": patch, "expect": [], "clean": False,
            "note": f"real code from {rev}; not ground truth",
            "file_text": "" if f.get("status") == "added" else read_file(repo, rev, str(f["filename"])),
        })
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    Path(path).expanduser().write_text(json.dumps(cases, indent=1), encoding="utf-8")
    return len(cases)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--range", default=None, help="a git revision range, A..B or A...B")
    ap.add_argument("--repo", default=str(BACKEND.parent), help="the repository to read (default: this one)")
    ap.add_argument("--ctx", default="16384,32768", help="comma-separated context sizes to price")
    ap.add_argument("--emit-cases", default=None, help="write the range's files as a prompt_eval case file")
    ap.add_argument("--emit-corpus-cases", default=None, help="write the committed cases as a bare JSON list")
    ap.add_argument("--pad", action="store_true", help="with --emit-corpus-cases: synthesise a file around each hunk")
    ap.add_argument("--redteam", action="store_true", help="with --emit-corpus-cases: include the hostile corpus")
    args = ap.parse_args(argv)

    try:
        sizes = [int(s) for s in args.ctx.split(",") if s.strip()]
    except ValueError:
        print("file_context_budget: --ctx takes comma-separated integers", file=sys.stderr)
        return 2
    if args.emit_corpus_cases:
        cases, unpadded = case_dicts(args.pad, args.redteam)
        path = Path(args.emit_corpus_cases).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cases, indent=1), encoding="utf-8")
        padded = sum(1 for c in cases if c.get("file_text"))
        print(f"{len(cases)} cases written to {path} ({padded} with file text)")
        if unpadded:
            print(f"no clean case of the same language to pad with, so these carry no file: {', '.join(unpadded)}",
                  file=sys.stderr)
    if not args.range:
        if not args.emit_corpus_cases:
            print("file_context_budget: give --range, --emit-corpus-cases, or both", file=sys.stderr)
            return 2
        return 0
    try:
        text = git_diff(str(Path(args.repo).resolve()), args.range)
    except CannotRun as e:
        print(f"file_context_budget: {e}", file=sys.stderr)
        return 2
    raw_files = split_git_diff(text)
    if not raw_files:
        print(f"nothing in {args.range}")
        return 0
    # the App's own eligibility rule decides which files a review would read, so the summary
    # prices what would actually be sent rather than every file in the range
    settings = settings_at(sizes[0])
    selected, skipped = select_files(raw_files, settings)
    reasons = dict(skipped)
    chosen = {str(f["filename"]) for f in selected}
    for f in raw_files:
        f["skip"] = "" if str(f["filename"]) in chosen else reasons.get(str(f["filename"]), "not selected")
    rev = head_of(args.range)
    repo = str(Path(args.repo).resolve())
    rows = measure(raw_files, repo, rev, sizes)
    print(f"range {args.range} ({len(raw_files)} files, {len(selected)} of them reviewed), "
          f"files read at {rev or 'the working tree'}")
    print_table(rows, sizes)
    print_summary(rows, sizes)
    if args.emit_cases:
        written = emit_cases_from_range(args.emit_cases, rows, repo, rev, raw_files)
        print(f"\n{written} cases written to {args.emit_cases}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
