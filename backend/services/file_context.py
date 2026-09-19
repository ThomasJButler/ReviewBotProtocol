"""How much of the file the hunk came from can be sent beside it, and what that
listing looks like.

A leaf module on purpose: the reviewer needs this arithmetic and cannot import
services/review_runner.py, because the runner imports the reviewer. So the two
constants the size gate is built on live here and the runner imports them from
here.

The listing is plain file text with one nonce-labelled header per span, no
per-line numbers and no plus marks. Nothing in the pipeline reads a number
printed beside a file line (services/diff.py locates evidence against the
patch's own numbering), while a number or a marker inside the block would be
one more token a hostile file could forge into a line of the change. The label
carries the request's nonce and MARK_FILE joins the reviewer's marker
alternation, so a forged label is defanged like a forged delimiter.

No git or GitHub reader lives here: services/github_client.py fetches the file
in production and services/git_diff.py reads it offline."""

import base64
import binascii
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from config.settings import Settings
from services.diff import hunk_spans, parse_patch

BYTES_PER_TOKEN = 2.8          # conservative for code
PROMPT_OVERHEAD_TOKENS = 1400  # system prompt, schema and framing: measured up to 1206 on 2026-09-06
                               # for the 699-word prompt (scripts/prompt_overhead.py), with headroom
MAX_FILE_BYTES = 1_000_000     # GitHub's own contents API limit, not a knob of ours
FETCH_SECONDS_PER_FILE = 5.0   # one contents call; _request may sleep on a throttle, so it is cancelled instead
FETCH_SECONDS_TOTAL = 60.0     # the whole fetch phase, whatever the file count
FETCH_CONCURRENCY = 4          # polite against one host and enough to hide the latency


@dataclass
class Rendered:
    """What review_file puts in the prompt: which of the three shapes was
    chosen, the block itself (empty for "none"), and the spans of the file the
    block holds, so the boundary check knows how many labels to expect."""

    mode: str                                     # whole, window or none
    block: str = ""
    spans: List[Tuple[int, int]] = field(default_factory=list)  # first and last line of each span, 1-based

    @property
    def markers(self) -> int:
        return len(self.spans)


def fits_context(patch: str, settings: Settings) -> bool:
    """Whether the patch alone leaves room for the prompt and the reply. The
    size gate asks this and nothing else, which is why turning file context on
    can never change which files are skipped: a patch that fills the budget
    simply gets no context."""
    tokens = len(patch.encode("utf-8")) / BYTES_PER_TOKEN
    return tokens + PROMPT_OVERHEAD_TOKENS + settings.OLLAMA_NUM_PREDICT <= settings.OLLAMA_NUM_CTX


def budget_bytes(settings: Settings) -> int:
    """Bytes the patch and the file listing have between them: the context
    window less the reply and the prompt's own overhead, at 2.8 bytes a token.
    36,355 at 16384, 82,230 at 32768."""
    tokens = settings.OLLAMA_NUM_CTX - settings.OLLAMA_NUM_PREDICT - PROMPT_OVERHEAD_TOKENS
    return max(0, int(tokens * BYTES_PER_TOKEN))


def spans(hunks: List[Tuple[int, int]], lines_total: int, window: int) -> List[Tuple[int, int]]:
    """Each hunk grown by `window` lines either side, clipped to the file, with
    overlapping and touching spans merged so no line of the file is listed
    twice and two hunks near each other read as one piece of code."""
    grown = sorted((max(1, start - window), min(lines_total, end + window))
                   for start, end in hunks if start <= lines_total)
    merged: List[Tuple[int, int]] = []
    for start, end in grown:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _label(marker: str, start: int, end: int, total: int, whole: bool) -> str:
    if whole:
        return f"{marker} the whole file at this commit, {total} lines"
    return f"{marker} lines {start} to {end} of {total}"


def _listing(lines: List[str], chosen: List[Tuple[int, int]], marker: str, whole: bool) -> str:
    """One label line per span and then the file's own text, verbatim. The
    leading blank line is part of the block, because the human template joins
    it straight onto the diff: an empty block must render the message the
    benchmarks measured, byte for byte."""
    parts: List[str] = []
    for start, end in chosen:
        parts.append(_label(marker, start, end, len(lines), whole))
        parts.append("\n".join(lines[start - 1:end]))
    return "\n\n" + "\n".join(parts) if parts else ""


def render(file_text: str, patch: str, settings: Settings, marker: str) -> Rendered:
    """The block to send beside this patch: the whole file when it fits the
    bytes the patch leaves, else the windows around each hunk, else nothing.

    The rendered bytes are what is measured, labels included, rather than the
    raw file, so the budget cannot be broken by the framing. An added file is
    its own listing, so it gets none: there is one rule for that here and one
    status skip in the runner, and no third constant."""
    if not file_text.strip():
        return Rendered("none")
    lines = file_text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # a trailing newline is not a line of the file
    total = len(lines)
    if not total:
        return Rendered("none")
    parsed = parse_patch(patch)
    if len(parsed.added_lines) >= total:
        return Rendered("none")  # the diff already holds every line this file has
    room = budget_bytes(settings) - len(patch.encode("utf-8"))
    if room <= 0:
        return Rendered("none")

    def fits(block: str) -> bool:
        return len(block.encode("utf-8")) <= room

    whole = [(1, total)]
    block = _listing(lines, whole, marker, whole=True)
    if fits(block):
        return Rendered("whole", block, whole)
    chosen = spans(hunk_spans(patch), total, settings.FILE_CONTEXT_LINES)
    # Windows are dropped from the end rather than shrunk: the first hunks keep the
    # context the reviewer reads first, and the window stays the size the round measured.
    while chosen:
        block = _listing(lines, chosen, marker, whole=False)
        if fits(block):
            return Rendered("window", block, list(chosen))
        chosen.pop()
    return Rendered("none")


def decode(raw_base64: str) -> Optional[str]:
    """The contents API's base64 payload as text, or None when it is not text
    this pipeline will send a model: too big, not UTF-8, or holding a NUL byte,
    which is how a binary file arrives."""
    try:
        raw = base64.b64decode(raw_base64 or "", validate=False)
    except (binascii.Error, ValueError):
        return None
    if not raw or len(raw) > MAX_FILE_BYTES or b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
