"""Split one multi-file `git diff` into the per-file dicts the review pipeline
consumes, shaped like the entries GitHub's pull request files API returns
(filename, status, patch, additions, deletions, previous_filename), so that
select_files and prepare_files in services/review_runner.py take them
unchanged.

Each file's patch starts at its first hunk header. services/diff.py parses
GitHub's hunk-only patch and would read a `+++ b/name` line as an added line
and a `diff --git` line as context (its in_hunk flag is never reset), so no
header line may ever reach it. Pure text and no subprocess: the caller runs
git, reads a .diff file, or reads stdin."""

import re
from typing import Dict, List, Optional

GITHUB_CONTEXT_LINES = 3  # git's default and GitHub's; the pipeline's line numbers assume it

_SECTION = "diff --git "
_COMBINED = ("diff --cc ", "diff --combined ")  # a merge commit shown against both parents; not reviewable per file
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
_STATUS_LINES = (
    ("new file mode", "added"),
    ("deleted file mode", "removed"),
    ("rename from ", "renamed"),
    ("copy from ", "copied"),
)
_OCTAL = re.compile(r"\\([0-7]{3})")
_SIMPLE_ESCAPES = {"\\": "\\", '"': '"', "t": "\t", "n": "\n", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}


def split_git_diff(text: str) -> List[Dict[str, object]]:
    """Every file section of a git diff as a GitHub-shaped dict, in order."""
    return [file_from_section(section) for section in split_sections(text)]


def split_sections(text: str) -> List[str]:
    """Cut the diff on lines beginning `diff --git `. A hunk body line always
    begins with '+', '-', ' ' or '\\', so a diff quoted inside a diff cannot
    open a section; text before the first header (a commit message from
    `git show`, a mail header) is dropped."""
    sections: List[str] = []
    current: List[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith(_SECTION) or line.startswith(_COMBINED):
            if current:
                sections.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        sections.append("\n".join(current))
    return sections


def file_from_section(section: str) -> Dict[str, object]:
    """One section into {filename, status, patch, additions, deletions,
    previous_filename}. Names come from the `+++`/`---` lines, then the rename
    or copy lines, then the `diff --git` line, so a name with a space or a
    C-quoted name survives every shape git prints."""
    lines = section.split("\n")
    if lines and lines[0].startswith(_COMBINED):
        name = lines[0].split(" ", 2)[2] if lines[0].count(" ") >= 2 else ""
        return {"filename": _unquote(name), "status": "combined", "patch": "", "additions": 0, "deletions": 0, "previous_filename": ""}
    header: List[str] = []
    body_start: Optional[int] = None
    for i, line in enumerate(lines):
        if _HUNK.match(line):
            body_start = i
            break
        header.append(line)
    status = "modified"
    old_name = new_name = rename_from = rename_to = ""
    for line in header:
        for prefix, value in _STATUS_LINES:
            if line.startswith(prefix):
                status = value
        if line.startswith("rename from ") or line.startswith("copy from "):
            rename_from = line.split(" from ", 1)[1]
        elif line.startswith("rename to ") or line.startswith("copy to "):
            rename_to = line.split(" to ", 1)[1]
        elif line.startswith("--- "):
            old_name = _strip_prefix(line[4:])
        elif line.startswith("+++ "):
            new_name = _strip_prefix(line[4:])
    a_name, b_name = _names_from_header(header[0] if header else "")
    filename = new_name or _unquote(rename_to) or b_name or old_name or a_name
    previous = old_name if status in ("renamed", "copied") and old_name else _unquote(rename_from) or (a_name if status in ("renamed", "copied") else "")
    body = lines[body_start:] if body_start is not None else []
    patch = "\n".join(body).rstrip("\n")
    additions = sum(1 for line in body if line.startswith("+") and not _HUNK.match(line))
    deletions = sum(1 for line in body if line.startswith("-") and not _HUNK.match(line))
    return {
        "filename": filename,
        "status": status,
        "patch": patch,
        "additions": additions,
        "deletions": deletions,
        "previous_filename": previous if status in ("renamed", "copied") else "",
    }


def _strip_prefix(raw: str) -> str:
    """The name on a `---` or `+++` line: the text up to the tab git appends
    after a name with a space, unquoted, without its a/ or b/ prefix. The
    empty string for /dev/null, so a caller can fall through."""
    name = _unquote(raw.split("\t", 1)[0])
    if name == "/dev/null":
        return ""
    if name.startswith("a/") or name.startswith("b/"):
        return name[2:]
    return name


def _names_from_header(line: str) -> "tuple[str, str]":
    """The two names on a `diff --git a/X b/Y` line. Quoted names are read
    as quoted tokens; for unquoted names the split is the one where the a/
    half and the b/ half agree, which is the only way to read an unquoted
    space, and a rename resolves its names from its own lines instead."""
    if not line.startswith(_SECTION):
        return "", ""
    rest = line[len(_SECTION):]
    if rest.startswith('"'):
        first, remainder = _read_quoted(rest)
        second = remainder.strip()
        return _drop_ab(_unquote(first)), _drop_ab(_unquote(second))
    for i in range(len(rest)):
        if rest[i] == " " and rest[:i].startswith("a/") and rest[i + 1:].startswith("b/") and rest[2:i] == rest[i + 3:]:
            return rest[2:i], rest[i + 3:]
    parts = rest.split(" ", 1)
    return _drop_ab(_unquote(parts[0])), _drop_ab(_unquote(parts[1] if len(parts) > 1 else ""))


def _drop_ab(name: str) -> str:
    return name[2:] if name.startswith("a/") or name.startswith("b/") else name


def _read_quoted(text: str) -> "tuple[str, str]":
    """Split a C-quoted token off the front of text, keeping its quotes."""
    i = 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return text[: i + 1], text[i + 1:]
        i += 1
    return text, ""


def _unquote(name: str) -> str:
    """git's C-style quoting: a name in double quotes with backslash escapes
    and octal bytes for anything outside printable ASCII."""
    if len(name) < 2 or not (name.startswith('"') and name.endswith('"')):
        return name
    inner = name[1:-1]
    out = bytearray()
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            m = _OCTAL.match(inner, i)
            if m:
                out.append(int(m.group(1), 8))
                i += 4
                continue
            nxt = inner[i + 1]
            out.extend(_SIMPLE_ESCAPES.get(nxt, nxt).encode("utf-8"))
            i += 2
            continue
        out.extend(ch.encode("utf-8"))
        i += 1
    return out.decode("utf-8", errors="replace")
