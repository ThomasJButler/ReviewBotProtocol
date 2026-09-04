"""Unified-diff helpers for the `patch` field GitHub returns per file.

GitHub's patch has hunks only, no `diff --git` header. We need the set of
new-file line numbers that appear in the diff (added and context lines),
because those are the only lines a review comment can attach to, and the
text of each so a finding's quoted evidence can be checked."""

import re
from dataclasses import dataclass, field
from typing import Tuple, Dict, Optional

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_TOKENS = re.compile(r"[A-Za-z0-9_]+")
MIN_EVIDENCE_CHARS = 8
MIN_EVIDENCE_TOKENS = 2


@dataclass
class ParsedPatch:
    new_lines: Dict[int, str] = field(default_factory=dict)   # line number -> text, added and context lines
    added_lines: Dict[int, str] = field(default_factory=dict)  # subset that was added
    hunks: int = 0

    def is_commentable(self, line: int) -> bool:
        return line in self.new_lines


def parse_patch(patch: Optional[str]) -> ParsedPatch:
    parsed = ParsedPatch()
    if not patch:
        return parsed
    new_no = 0
    in_hunk = False
    for raw in patch.replace("\r\n", "\n").rstrip("\n").split("\n"):
        m = _HUNK.match(raw)
        if m:
            new_no = int(m.group(3))
            in_hunk = True
            parsed.hunks += 1
            continue
        if not in_hunk:
            continue
        if raw.startswith("\\"):        # "\ No newline at end of file"
            continue
        if raw.startswith("+"):
            parsed.new_lines[new_no] = raw[1:]
            parsed.added_lines[new_no] = raw[1:]
            new_no += 1
        elif raw.startswith("-"):
            continue
        else:
            text = raw[1:] if raw.startswith(" ") else raw
            parsed.new_lines[new_no] = text
            new_no += 1
    return parsed


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _evidence_forms(evidence: str) -> list:
    """The model sees the raw diff, so it may quote the line with its '+', '-'
    or ' ' marker. Try both the quoted form and the marker-stripped form."""
    ev = _norm(evidence)
    forms = [ev]
    if ev and ev[0] in "+- " and len(ev) > 1:
        forms.append(_norm(ev[1:]))
    return [f for f in forms if f]


def _substantial(ev: str) -> bool:
    return len(ev) >= MIN_EVIDENCE_CHARS or len(_TOKENS.findall(ev)) >= MIN_EVIDENCE_TOKENS


def locate_evidence_part(parsed: ParsedPatch, line: int, evidence: str) -> Tuple[Optional[int], str]:
    """Where in the new file the quoted evidence really is, and which part of
    the quote sits there. A model that quotes several lines is located by the
    first of them that is in the diff, and only that line is kept as the
    finding's evidence, so a fabricated line cannot ride along with a real
    one into the posted comment."""
    if evidence and "\n" in evidence.strip():
        for offset, part in enumerate(p for p in evidence.splitlines() if p.strip()):
            located = _locate_single(parsed, line + offset, part)
            if located is not None:
                return located, part
        return None, evidence
    return _locate_single(parsed, line, evidence), evidence


def locate_evidence(parsed: ParsedPatch, line: int, evidence: str) -> Optional[int]:
    return locate_evidence_part(parsed, line, evidence)[0]


def _locate_single(parsed: ParsedPatch, line: int, evidence: str) -> Optional[int]:
    """Return the line the evidence actually sits on: the claimed line if it
    matches, otherwise the nearest line in the diff that contains the quote.
    None if the quote is not in the diff at all (a hallucinated quote), or
    too short to mean anything."""
    forms = _evidence_forms(evidence)
    if not forms or not any(_substantial(f) for f in forms):
        return None
    forms = [f for f in forms if _substantial(f)]
    if line in parsed.new_lines and any(f in _norm(parsed.new_lines[line]) for f in forms):
        return line
    candidates = [no for no, text in parsed.new_lines.items() if any(f in _norm(text) for f in forms)]
    if not candidates:
        return None
    added = [no for no in candidates if no in parsed.added_lines]
    pool = added or candidates
    return min(pool, key=lambda no: (abs(no - line), no))
