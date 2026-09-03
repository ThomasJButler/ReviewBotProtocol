"""Turn file results into one PR review: a body and inline comments.

Everything the model wrote passes through sanitise(): HTML removed, links
kept only to github.com (including GitHub's www. and e-mail autolinks and
reference-style definitions), @mentions neutralised, length bounded. Quoted
evidence goes inside a code span, where GitHub renders nothing as markup, so
it only loses backticks and newlines. The footer says which model wrote it."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from services.ai_reviewer import FileReviewResult
from services.schemas import SEVERITY_ORDER, Severity

FOOTER = ("Generated locally by ReviewBot Protocol using `{model}` via Ollama. "
          "Findings are model output and may be wrong; verify before acting.")

_HTML_TAG = re.compile(r"<[^>]*>", re.S)
_REF_DEF = re.compile(r"^[ \t]*\[[^\]\n]+\]:[ \t]*\S.*$", re.M)
_MD_LINK = re.compile(r"!?\[([^\]]{0,200})\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_BARE_URL = re.compile(r"(?:https?://|www\.)[^\s)\]>]+", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_MENTION = re.compile(r"@(?=[A-Za-z0-9])")
_BLANKS = re.compile(r"\n{3,}")


def _github_url(url: str) -> bool:
    try:
        parts = urlparse(url)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    host = (parts.hostname or "").lower()
    return host == "github.com" or host.endswith(".github.com")


def sanitise(text: str, limit: int, code: bool = False) -> str:
    """Model text made safe to post. With code=True the text is destined for a
    code span, where GitHub renders no markup, so only backticks and
    newlines are removed."""
    if not text:
        return ""
    out = str(text)
    if code:
        out = out.replace("`", "").replace("\n", " ").replace("\r", " ").strip()
    else:
        out = _HTML_TAG.sub("", out)
        out = _REF_DEF.sub("", out)
        out = _MD_LINK.sub(lambda m: m.group(0).lstrip("!") if _github_url(m.group(2)) else m.group(1), out)
        out = _BARE_URL.sub(lambda m: m.group(0) if _github_url(m.group(0) if "://" in m.group(0) else "https://" + m.group(0)) else "[link removed]", out)
        out = _EMAIL.sub(lambda m: m.group(0).replace("@", "＠"), out)
        out = _MENTION.sub("＠", out)
        out = _BLANKS.sub("\n\n", out).strip()
    if len(out) > limit:
        out = out[: max(0, limit - 14)].rstrip() + ("" if code else "\n") + "[truncated]"
    return out


@dataclass
class RenderedReview:
    body: str
    comments: List[Dict] = field(default_factory=list)
    findings_total: int = 0
    counts_by_severity: Dict[str, int] = field(default_factory=dict)


def _inline_body(sev: Severity, category: str, title: str, recommendation: str, evidence: str) -> str:
    text = f"**{sev.value.capitalize()} {category}: {sanitise(title, 120)}**\n\n{sanitise(recommendation, 600)}"
    ev = sanitise(evidence, 300, code=True)
    if ev:
        text += f"\n\n`{ev}`"
    return text[:2000]


def render_review(results: Sequence[FileReviewResult], *, model: str, skipped: Sequence[Tuple[str, str]] = (),
                  is_fork: bool = False, fork_repo: Optional[str] = None, max_inline: int = 25,
                  redaction_total: int = 0, files_errored: int = 0) -> RenderedReview:
    all_findings = []
    for r in results:
        for f in r.review.findings:
            all_findings.append((r.filename, f))
    all_findings.sort(key=lambda x: (SEVERITY_ORDER[x[1].severity], x[0], x[1].line))
    counts: Dict[str, int] = {}
    for _, f in all_findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1

    comments: List[Dict] = []
    overflow = []
    for path, f in all_findings:
        if len(comments) < max_inline:
            comments.append({"path": path, "line": f.line, "side": "RIGHT",
                             "body": _inline_body(f.severity, f.category.value, f.title, f.recommendation, f.evidence)})
        else:
            overflow.append((path, f))

    lines = ["## ReviewBot review", ""]
    if files_errored:
        lines.append(f"Warning: the model did not return a usable review for {files_errored} file{'s' if files_errored != 1 else ''}; they are listed under Not reviewed.")
    if all_findings:
        parts = [f"{counts[s.value]} {s.value}" for s in Severity if counts.get(s.value)]
        lines.append(f"{len(all_findings)} finding{'s' if len(all_findings) != 1 else ''} across {len(results)} reviewed file{'s' if len(results) != 1 else ''} ({', '.join(parts)}).")
    else:
        lines.append(f"No findings in {len(results)} reviewed file{'s' if len(results) != 1 else ''}.")
    if is_fork:
        lines.append(f"This pull request comes from the fork `{sanitise(fork_repo or '(deleted fork)', 200, code=True)}`.")
    if redaction_total:
        lines.append(f"{redaction_total} credential-looking value{'s were' if redaction_total != 1 else ' was'} redacted before review. Check the diff for committed secrets.")
    lines.append("")

    for r in results:
        summary = sanitise(r.review.summary, 500) or "No summary."
        lines.append(f"- `{sanitise(r.filename, 200, code=True)}`: {summary}")
    lines.append("")

    if overflow:
        lines.append(f"### {len(overflow)} further finding{'s' if len(overflow) != 1 else ''} not attached inline")
        lines.append("")
        for path, f in overflow:
            lines.append(f"- `{sanitise(path, 200, code=True)}` line {f.line}, {f.severity.value} {f.category.value}: {sanitise(f.title, 120)}")
        lines.append("")

    if skipped:
        lines.append("### Not reviewed")
        lines.append("")
        for path, reason in skipped:
            lines.append(f"- `{sanitise(path, 200, code=True)}`: {sanitise(reason, 160)}")
        lines.append("")

    lines.append("---")
    footer = FOOTER.format(model=sanitise(model, 100, code=True))
    lines.append(footer)
    body = "\n".join(lines)
    if len(body) > 6000:
        body = body[: 6000 - len(footer) - 20].rstrip() + "\n[truncated]\n\n---\n" + footer
    return RenderedReview(body=body, comments=comments, findings_total=len(all_findings), counts_by_severity=counts)
