"""One structured model call per file, then post-processing against the diff.

The chain is prompt | model bound to the JSON schema. The reply is parsed
leniently (a model that adds a fence or an extra field does not lose the
whole review), validated against the schema, and then every finding is
checked against the patch: the quoted evidence must actually be in the diff,
the line must be a line a comment can attach to, and confidence must clear
the floor. Findings that fail are dropped, not posted."""

import asyncio
import json
import re
import secrets
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from config.logging import get_logger
from config.settings import CONTEXT_LINE_DEFAULT, CONTEXT_LINE_MIN_CONFIDENCE_DEFAULT, Settings
from services.diff import locate_evidence_kind, parse_patch
from services.prompts import MARK_BEGIN, MARK_END, cross_prompt, delimiters, review_prompt, verify_prompt
from services.redaction import redact_text
from services.schemas import (SEVERITY_ORDER, AnnotatedFileReview, CrossExamination, FileReview, Finding, ReviewedFinding,
                              Severity, Verdict, cross_schema, output_schema, verdict_schema)

logger = get_logger(__name__)
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
# Bounded, newline-free repeats on both sides: the engine tries at most 16 characters
# before the literal at any position, so a line of 32,000 '<' costs linear time, and a
# marker never swallows the line break before it (line numbers stay honest). Brackets
# beyond the bound are left behind on their own, which cannot rebuild a delimiter
# because the marker name itself is gone.
_MARKER = re.compile(rf"[<\t ]{{0,16}}(?:{MARK_BEGIN}|{MARK_END})[A-Za-z0-9_]{{0,64}}[\t >]{{0,16}}")


TAG_WORDS = {"yagni", "delete", "stdlib", "native", "shrink"}
# the words a bare tag list is strung together with, and the words of the instruction itself
_TAG_GLUE = {"and", "or", "then", "the", "a", "to", "what", "remove", "never", "tag", "alone", "use"}
_PROMPT_ECHO = re.compile(r"never the tag alone|then what to remove", re.I)
_TITLE_WORDS = re.compile(r"[^a-z]+")


def _tag_only_title(title: str) -> bool:
    """A simplicity finding titled with the tag rather than the problem, which both
    prompts forbid ("then what to remove, never the tag alone"): the model filling
    the slot. Three shapes, all seen live: the tag alone ("shrink"), the tag list
    ("yagni, delete, shrink"), and the prompt's own sentence copied out ("yagni,
    delete, stdlib, native or shrink, then what to remove, never the tag alone",
    42 of those in round three's raw replies). A tag word in front of something
    real ("yagni, delete unused import") is the form the prompt asks for and stays."""
    t = title.strip().lower().rstrip(".:")
    if t in TAG_WORDS:
        return True
    words = [w for w in _TITLE_WORDS.split(t) if w]
    return bool(words) and any(w in TAG_WORDS for w in words) and all(w in TAG_WORDS or w in _TAG_GLUE for w in words) \
        and not _PROMPT_ECHO.search(t)


def _instruction_title(title: str) -> bool:
    """The prompt's own sentence copied into the title slot. The finding under it is
    often right (round three: "yagni, delete, stdlib, native or shrink, then what to
    remove" on the factory class it was meant to find), so the title is replaced from
    the recommendation rather than the finding dropped."""
    return bool(_PROMPT_ECHO.search(title.strip().lower()))


def _title_from(recommendation: str) -> str:
    """A title for a finding whose own title says nothing: the recommendation's first
    sentence, which is where the model put the substance."""
    first = re.split(r"(?<=[.!?])\s", recommendation.strip(), maxsplit=1)[0].strip()
    return (first[:117].rstrip() + "...") if len(first) > 120 else first


_NOTHING = {"", "none", "n/a", "na", "no finding", "no findings", "nothing", "-"}


def _null_addition(f) -> bool:
    """An addition that says it is nothing (title "none", recommendation "N/A"):
    the second model filling the slot rather than raising a problem. Round three
    found one of these landing on a refuted line and, through the correction
    rule, restoring the false positive the model had just refuted."""
    return f.title.strip().lower() in _NOTHING or f.recommendation.strip().lower() in _NOTHING


# Each subject word is whitespace-free and eats its own trailing space, so the parts cannot
# overlap. The earlier form allowed the middle to match spaces between two \s+ quantifiers,
# which made a long run of them cost quadratic backtracking on the event loop: 2.8 s for one
# 600-character recommendation, measured 2026-09-08 (CLAUDE-SECURITY-20260908-004806, F2).
_SUBJECT = r"(?:(?:the|this|that|these|those|it|which|your|current)\s+(?:[^\s.;:!?]{1,40}\s+){0,12})?"
_PRAISE = re.compile(
    rf"^{_SUBJECT}(?:"
    r"(?:is|are|looks?|seems?|remains?|works?)\s+(?:already\s+|now\s+)?(?:the\s+)?"
    r"(?:correct|correctly|fine|good|safe|right|proper|acceptable|appropriate|sufficient|adequate|valid|as\s+expected|as\s+intended)"
    r"(?:\s+(?:fix|approach|choice|way|pattern|solution|thing))?\b|"
    # inflected only: "correctly implements" is praise, "correctly implement" is an instruction
    r"(?:correctly|properly|already)\s+(?:implement|handle|use|appl|escape|valid|sanitis|sanitiz|prevent|protect|cover|address|guard)"
    r"\w*(?:s|ed|ing)\b|"
    r"no\s+(?:change|action|fix|issue|problem|further)s?\b|"
    r"nothing\s+(?:to\s+(?:change|fix|do)|needs?|further)\b|"
    r"well[-\s](?:implemented|handled|done|written)\b|"
    r"(?:is\s+)?(?:a\s+)?good\s+practice\b|"
    r"keep\s+(?:it\s+|this\s+)?as\s+is\b|"
    r"as\s+(?:is|expected|intended)\b)", re.I)
_ASK_VERB = (r"(?:add|use|replace|remove|move|rename|wrap|validate|escape|parameteri[sz]e|sanitis|sanitiz|check|guard|catch|close|lock|"
             r"encrypt|hash|set|call|avoid|prefer|consider|ensure|make|change|fix|update|handle|return|raise|throw|log|limit|restrict|"
             r"restore|re-add|switch|convert|introduce|extract|define|declare|store|drop|delete|rewrite|split|apply|enable|disable|"
             r"verify|test|document)\w*")
# an ask is a verb opening a clause, or a modal anywhere; "to ensure" inside a sentence of praise is not one
_ASK = re.compile(rf"(?:^|[.;:,!?]\s*|\b(?:but|and|or|then|so|also|instead|however)\s+)(?:please\s+|also\s+|instead\s+)?{_ASK_VERB}\b"
                  r"|\b(?:should|must|needs?\s+to|ought\s+to|recommend\w*|suggest\w*)\b", re.I)
# Praise that turns a corner is a finding: "is correct, but fails when the input is empty".
_CONTRAST = re.compile(r"\b(?:but|however|although|though|except|unless|until|whereas|yet|still|otherwise|caveat|"
                       r"whilst|while|apart\s+from|other\s+than)\b", re.I)
_DEFECT = re.compile(r"\b(?:fail|fails|failed|failing|break|breaks|broken|breaking|leak|leaks|leaking|crash|crashes|"
                     r"raise|raises|throw|throws|ignore|ignores|ignoring|miss|misses|missing|expose|exposes|exposing|"
                     r"raced?|races|hang|hangs|overflow|overflows|truncat\w*|silently|incorrect\w*|wrong|unsafe|"
                     r"vulnerab\w*|injection|traversal|absent|undefined|null\s+pointer)\b", re.I)


def _praise(f) -> bool:
    """A recommendation that opens by saying the code is right and then asks
    for nothing, warns of nothing and turns no corner: praise filed as a
    finding, or a finding whose recommendation is nothing at all. Round three,
    on a clean control: "Status element lacks aria-live region", recommendation
    "The addition of `role="status"` and `aria-live="polite"` is correct for a
    dynamic save status message to ensure screen readers announce updates", in
    both repeats of both reviewer candidates, and it passed every rule the
    postprocess had.

    Everything after the praise decides it, because praise is how a real
    finding often opens: "No change is needed here, but add a test" asks,
    "is correct in the common case, but fails when the input is empty" turns
    a corner, and "correctly validate the input" is an instruction wearing
    the same word. Dropping one of those would lose a real finding and leave
    only a log line, so each of the three keeps it."""
    text = f.recommendation.strip()
    if text.lower() in _NOTHING:
        return True
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0][:200]  # a praise clause is never longer
    m = _PRAISE.match(first)
    if not m:
        return False
    rest = text[m.end():]
    return not (_ASK.search(rest) or _CONTRAST.search(rest) or _DEFECT.search(rest))


class PromptBoundaryError(RuntimeError):
    """The rendered prompt did not contain exactly one begin and one end delimiter."""


def _defang(text: str) -> str:
    """Anything in PR content that resembles a data delimiter, with any number
    of angle brackets and any nonce suffix, is rewritten to a bracket-free
    token that says what it is: the verifier read the old `[data-marker]` as
    the pipeline's own framing and stood down (round three). The replacement contains no angle brackets, so it cannot be
    reassembled into a delimiter by a second pass."""
    return _MARKER.sub("[forged-data-marker]", text)


def _meta(value: str, limit: int = 200) -> str:
    """Filenames and labels come from the PR. Keep only printable characters
    that are not format, line or paragraph separators, so nothing can break
    out of its line in the prompt or hide text with bidi controls."""
    cleaned = "".join(c for c in str(value or "") if c.isprintable() and unicodedata.category(c) not in ("Cf", "Zl", "Zp"))
    return _defang(cleaned)[:limit]


@dataclass
class FileReviewResult:
    filename: str
    language: str
    status: str
    review: AnnotatedFileReview
    dropped: int = 0
    parse_ok: bool = True
    prompt_tokens: int = 0
    output_tokens: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    refuted: int = 0        # findings the verify pass rejected
    verify_calls: int = 0   # verify calls made (one per finding that reached the pass)
    cross_calls: int = 0    # cross-examiner calls (one per file)
    cross_refuted: int = 0  # findings the cross-examiner refuted
    cross_added: int = 0    # findings the cross-examiner added that survived postprocess
    redactions: Dict[str, int] = field(default_factory=dict)
    patch: str = ""         # the redacted patch, kept so a later cross-examination phase can run on it


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _coerce_finding(item: Any) -> Optional[Finding]:
    if not isinstance(item, dict):
        return None
    d = dict(item)
    for key, limit in (("title", 120), ("evidence", 300), ("recommendation", 600)):
        v = d.get(key)
        d[key] = redact_text("" if v is None else str(v))[:limit]
    for key in ("category", "severity"):
        if isinstance(d.get(key), str):
            d[key] = d[key].strip().lower()
    line = d.get("line")
    if isinstance(line, str) and line.strip().isdigit():
        d["line"] = int(line.strip())
    conf = d.get("confidence", 0.7)
    try:
        d["confidence"] = min(1.0, max(0.0, float(conf)))
    except (TypeError, ValueError):
        d["confidence"] = 0.7
    try:
        return Finding.model_validate(d)
    except ValidationError:
        return None


def parse_file_review(text: str) -> Tuple[FileReview, bool]:
    """Lenient parse. Returns (review, parse_ok). Never raises."""
    cleaned = _FENCE.sub("", (text or "").strip()).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return FileReview(findings=[], summary="The model did not return a readable review."), False
    if isinstance(data, list):
        data = {"findings": data, "summary": ""}
    if not isinstance(data, dict):
        return FileReview(findings=[], summary="The model returned an unexpected shape."), False
    findings = [f for f in (_coerce_finding(i) for i in (data.get("findings") or [])) if f is not None][:20]
    summary = redact_text(str(data.get("summary") or ""))[:500]
    return FileReview(findings=findings, summary=summary), True


def parse_verdict(text: str) -> Optional[Verdict]:
    """The verifier's JSON, or None when it cannot be read. A verdict that
    cannot be read keeps the finding: the pass is a filter, not a gate on
    the model's health."""
    cleaned = _FENCE.sub("", (text or "").strip())
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        data["reason"] = redact_text(str(data.get("reason") or ""))[:300]
        conf = data.get("confidence")
        if isinstance(conf, (int, float)) and 1 < conf <= 100:
            data["confidence"] = conf / 100  # a model that answers in percent
        return Verdict.model_validate(data)
    except ValidationError:
        return None


def parse_cross_examination(text: str) -> Optional[CrossExamination]:
    """The cross-examiner's JSON, or None when it cannot be read (the first
    reviewer's findings then stand unchanged). Additions are coerced like
    first-pass findings; reasons and the note are redacted."""
    cleaned = _FENCE.sub("", (text or "").strip())
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    verdicts = []
    for item in (data.get("verdicts") or [])[:20]:
        if not isinstance(item, dict):
            continue
        v = dict(item)
        v["reason"] = redact_text(str(v.get("reason") or ""))[:300]
        conf = v.get("confidence")
        if isinstance(conf, (int, float)) and 1 < conf <= 100:
            v["confidence"] = conf / 100
        try:
            verdicts.append(v)
        except Exception:  # pragma: no cover
            continue
    additions = [f for f in (_coerce_finding(i) for i in (data.get("additions") or [])[:10]) if f is not None]
    note = redact_text(str(data.get("summary_note") or ""))[:300]
    try:
        return CrossExamination.model_validate({"verdicts": verdicts, "additions": additions, "summary_note": note})
    except ValidationError:
        # keep whatever verdicts validate on their own; a bad one is skipped, not fatal
        good = []
        for v in verdicts:
            try:
                CrossExamination.model_validate({"verdicts": [v], "additions": [], "summary_note": ""})
                good.append(v)
            except ValidationError:
                continue
        try:
            return CrossExamination.model_validate({"verdicts": good, "additions": additions, "summary_note": note})
        except ValidationError:
            return None


def annotate(review: FileReview, source_model: str) -> AnnotatedFileReview:
    """Stamp first-pass findings with the model that raised them."""
    return AnnotatedFileReview(findings=[ReviewedFinding(**f.model_dump(), source_model=source_model) for f in review.findings],
                               summary=review.summary)


def drop_rule(f: Finding, min_confidence: float) -> Optional[str]:
    """Why a finding is dropped before it is located, or None to go on. The
    harness applies the same rules to a raw reply so a leaderboard can count them."""
    if f.confidence < min_confidence:
        return "confidence"
    if _tag_only_title(f.title):
        return "tag_title"
    if _praise(f):
        return "praise"
    return None


def context_line_action(kind: str, f: Finding, policy: str, min_confidence: float) -> str:
    """keep, drop or downgrade a finding by where the locator put its evidence.

    A finding on a line the pull request never touched is a claim about code
    nobody asked about, and the live nights say it is nearly always noise. A
    quote of a line the change removed is never touched: the prompt asks for a
    removal to be reported on "the new-file line that now lacks it"
    (services/prompts.py), so a removal is a finding about the change itself.
    The kind is the locator's own answer, never a second predicate."""
    if kind != "context":
        return "keep"
    if policy == "drop":
        return "drop"
    if policy == "downgrade":
        return "downgrade"
    if policy == "confidence":
        return "keep" if f.confidence >= min_confidence else "drop"
    return "keep"


def _one_step_down(severity: Severity) -> Severity:
    """One step down SEVERITY_ORDER, info staying info: severity only ever goes
    down in this pipeline, as the cross-examiner and the verifier already have it."""
    order = list(Severity)
    return order[min(SEVERITY_ORDER[severity] + 1, len(order) - 1)]


def postprocess(review: FileReview, patch: Optional[str], min_confidence: float, *,
                filename: str = "", counts: Optional[Dict[str, int]] = None,
                context_policy: str = CONTEXT_LINE_DEFAULT,
                context_min_confidence: float = CONTEXT_LINE_MIN_CONFIDENCE_DEFAULT) -> Tuple[FileReview, int]:
    """The kept review and how many findings went. A caller that needs the drops
    broken down by rule, as the precision harness does, passes a dict as counts
    and gets it filled in by rule name: the alternative was a second copy of
    this loop somewhere else, which drifted from it. The context-line keywords
    default from the same constants the Settings fields default from, so a
    caller that passes no policy still gets the shipped one."""
    parsed = parse_patch(patch)
    kept: List[Finding] = []
    seen = set()

    def dropped(f: Finding, rule: str) -> None:
        if counts is not None:
            counts[rule] = counts.get(rule, 0) + 1
        # the title was redacted at parse time; the log is how a dropped finding is seen at all
        logger.info("finding dropped", rule=rule, filename=_meta(filename), line=f.line, title=f.title[:120])

    for f in review.findings:
        rule = drop_rule(f, min_confidence)
        if rule:
            dropped(f, rule)
            continue
        if _instruction_title(f.title) and _title_from(f.recommendation):
            logger.info("finding retitled", rule="instruction_title", filename=_meta(filename), line=f.line, title=f.title[:120])
            f = f.model_copy(update={"title": _title_from(f.recommendation)})
        located, part, kind = locate_evidence_kind(parsed, f.line, f.evidence)
        if located is None:
            dropped(f, "unlocated")
            continue
        action = context_line_action(kind, f, context_policy, context_min_confidence)
        if action == "drop":
            dropped(f, "context_line")
            continue
        key = (located, f.title.strip().lower())
        if key in seen:
            dropped(f, "duplicate")
            continue
        seen.add(key)
        if action == "downgrade":
            # counted and logged only for a finding that survives the dedupe, so the counter is what the review kept
            lower = _one_step_down(f.severity)
            if counts is not None:
                counts["context_line_downgraded"] = counts.get("context_line_downgraded", 0) + 1
            logger.info("finding downgraded", rule="context_line", filename=_meta(filename), line=located,
                        severity=lower.value, was=f.severity.value)
            f = f.model_copy(update={"severity": lower})
        if part != f.evidence:
            f = f.model_copy(update={"evidence": part.strip()[:300]})
        kept.append(f.model_copy(update={"line": located}))
    kept.sort(key=lambda x: (SEVERITY_ORDER[x.severity], x.line))
    return FileReview(findings=kept, summary=review.summary), len(review.findings) - len(kept)


class FileReviewer:
    def __init__(self, llm: BaseChatModel, settings: Settings, prompt=review_prompt,
                 verifier_prompt=verify_prompt, verify: Optional[bool] = None,
                 cross_llm: Optional[BaseChatModel] = None, cross_prompt_template=cross_prompt,
                 model_name: Optional[str] = None, cross_note_first: Optional[bool] = None):
        self.settings = settings
        self.prompt = prompt
        self.verifier_prompt = verifier_prompt
        self.verify_enabled = settings.VERIFY_FINDINGS if verify is None else verify
        self.verify_budget = settings.MAX_VERIFY_CALLS_PER_REVIEW  # shared across every file of one review
        self.chain = prompt | llm.bind(format=output_schema())
        self.verify_chain = verifier_prompt | llm.bind(format=verdict_schema())
        self.model_name = model_name or str(getattr(llm, "model", "") or "reviewer")
        self.cross_prompt = cross_prompt_template
        self.cross_model_name = str(getattr(cross_llm, "model", "") or "cross-examiner") if cross_llm is not None else ""
        note_first = settings.CROSS_EXAMINE_NOTE_FIRST if cross_note_first is None else cross_note_first
        self.cross_chain = (cross_prompt_template | cross_llm.bind(format=cross_schema(note_first=note_first))) if cross_llm is not None else None
        self.cross_budget = settings.CROSS_EXAMINE_MAX_CALLS_PER_REVIEW  # shared across every file of one review
        # review_file cross-examines each file as it goes; the workflow switches this off when it
        # runs the two models one at a time and calls cross_examine_file itself in a second phase
        self.cross_inline = True

    @property
    def cross_enabled(self) -> bool:
        return self.cross_chain is not None

    async def cross_examine_file(self, result: FileReviewResult) -> FileReviewResult:
        """The second model's pass over one finished file review, applied in place:
        the reconciled review, the counts and the tokens land on the result."""
        if self.cross_chain is None or result.error:
            return result
        started = time.perf_counter()
        result.review, refuted, added, calls, c_in, c_out = await self.cross_examine(
            result.review, result.patch, result.filename, result.language)
        result.cross_refuted += refuted
        result.cross_added += added
        result.cross_calls += calls
        result.prompt_tokens += c_in
        result.output_tokens += c_out
        result.duration_seconds += time.perf_counter() - started
        return result

    async def cross_examine(self, review: AnnotatedFileReview, patch: str, filename: str, language: str
                            ) -> Tuple[AnnotatedFileReview, int, int, int, int, int]:
        """One call to the second model per file: it judges each finding, adds
        what it believes was missed, and notes disagreements. Returns the
        reconciled review, refuted, added, calls, tokens in, tokens out.
        Fail open: anything unreadable leaves the first review unchanged."""
        if self.cross_chain is None:
            return review, 0, 0, 0, 0, 0
        if self.cross_budget <= 0:
            logger.warning("cross-examine budget exhausted for this review, findings left unexamined", filename=_meta(filename))
            return review, 0, 0, 0, 0, 0
        self.cross_budget -= 1
        data_begin, data_end = delimiters(secrets.token_hex(8))
        block = "\n".join(
            f"[{i}] {f.category.value} | {f.severity.value} | line {f.line} | {_meta(_defang(f.title), 120)} | evidence: {_meta(_defang(f.evidence), 300)}"
            for i, f in enumerate(review.findings)) or "(none)"
        inputs = {"filename": _meta(filename), "language": _meta(language, 40), "code_diff": await asyncio.to_thread(_defang, patch or ""),
                  "findings_block": block, "data_begin": data_begin, "data_end": data_end}
        human = _content_text(self.cross_prompt.format_messages(**inputs)[-1].content)
        if human.count(data_begin) != 1 or human.count(data_end) != 1 or human.index(data_begin) > human.index(data_end):
            logger.error("cross-examine prompt boundary check failed", filename=_meta(filename))
            return review, 0, 0, 0, 0, 0
        try:
            message = await self.cross_chain.ainvoke(inputs)
        except Exception as e:
            logger.warning("cross-examine call failed, first review stands", filename=_meta(filename), error=type(e).__name__)
            return review, 0, 0, 1, 0, 0
        usage = getattr(message, "usage_metadata", None) or {}
        tokens_in, tokens_out = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
        text = _content_text(message.content)
        if self.settings.LOG_PROMPTS:
            logger.info("cross-examiner output", filename=filename, output=redact_text(text)[:4000])
        ce = parse_cross_examination(text)
        if ce is None:
            logger.warning("cross-examiner output unreadable, first review stands", filename=_meta(filename))
            return review, 0, 0, 1, tokens_in, tokens_out
        floor = self.settings.MIN_FINDING_CONFIDENCE
        by_index = {v.index: v for v in ce.verdicts if 0 <= v.index < len(review.findings)}
        kept: List[ReviewedFinding] = []
        refuted = 0
        refuted_at: Dict[int, Tuple[ReviewedFinding, CrossVerdict]] = {}  # line -> what was refuted there
        for i, f in enumerate(review.findings):
            v = by_index.get(i)
            if v is None:
                kept.append(f)
                continue
            if not v.confirmed and v.confidence >= floor:
                refuted += 1
                refuted_at.setdefault(f.line, (f, v))
                logger.info("finding refuted by the cross-examiner", filename=_meta(filename), line=f.line, reason=v.reason[:200])
                continue
            severity = f.severity if SEVERITY_ORDER[f.severity] >= SEVERITY_ORDER[v.severity] else v.severity
            kept.append(f.model_copy(update={"severity": severity, "cross_verdict": v.verdict.value,
                                             "cross_reason": v.reason, "cross_severity": v.severity}))
        additions, _ = postprocess(FileReview(findings=ce.additions, summary=""), patch, floor, filename=filename,
                                   context_policy=self.settings.CONTEXT_LINE_FINDINGS,
                                   context_min_confidence=self.settings.CONTEXT_LINE_MIN_CONFIDENCE)
        seen = {(f.line, f.title.strip().lower()) for f in kept}
        # a line where the second model has just confirmed the first reviewer's finding: an addition
        # of the same category there is the same problem under a shorter title, not a new one
        confirmed = {(f.line, f.category) for f in kept if f.cross_verdict == "real"}
        added = 0
        for f in additions.findings:
            key = (f.line, f.title.strip().lower())
            if key in seen or _null_addition(f) or (f.line, f.category) in confirmed:
                continue
            if f.line in refuted_at and refuted_at[f.line][0].category == f.category:
                # "false positive" followed by the second model's own finding on the same line, in
                # the same category, is a correction of severity or wording, not a refutation: the
                # first reviewer's finding stands with its provenance, at the lowest severity anyone
                # gave it. A finding of another category on that line is a different problem and
                # stands on its own, and the refutation stands too.
                original, v = refuted_at.pop(f.line)
                lowest = max((original.severity, v.severity, f.severity), key=lambda s: SEVERITY_ORDER[s])  # most severe sorts first
                kept.append(original.model_copy(update={"severity": lowest, "cross_verdict": "real",
                                                        "cross_reason": v.reason, "cross_severity": f.severity}))
                seen.add((original.line, original.title.strip().lower()))
                refuted -= 1
                logger.info("cross-examiner corrected rather than refuted", filename=_meta(filename), line=f.line)
                continue
            seen.add(key)
            kept.append(ReviewedFinding(**f.model_dump(), source_model=self.cross_model_name, cross_verdict="real",
                                        cross_reason="", cross_severity=f.severity))
            added += 1
        kept.sort(key=lambda x: (SEVERITY_ORDER[x.severity], x.line))
        summary = review.summary or ""
        if ce.summary_note:
            note = f" Cross-examiner: {ce.summary_note.strip()}"
            summary = summary[: 500 - len(note)].rstrip() + note
        return AnnotatedFileReview(findings=kept, summary=summary), refuted, added, 1, tokens_in, tokens_out

    async def _verify(self, review: AnnotatedFileReview, patch: str, filename: str, language: str) -> Tuple[AnnotatedFileReview, int, int, int, int]:
        """Run every finding past the verifier. Returns the surviving review,
        how many were refuted, how many calls were made, and the tokens used.
        Severity can only go down. An unreadable or failed verdict keeps the
        finding and is logged."""
        kept: List[ReviewedFinding] = []
        refuted = calls = tokens_in = tokens_out = 0
        for f in review.findings:
            if self.verify_budget <= 0:
                logger.warning("verify budget exhausted for this review, keeping the remaining findings unverified", filename=_meta(filename))
                kept.append(f)
                continue
            self.verify_budget -= 1
            data_begin, data_end = delimiters(secrets.token_hex(8))
            inputs = {"filename": _meta(filename), "language": _meta(language, 40), "code_diff": await asyncio.to_thread(_defang, patch or ""),
                      "category": f.category.value, "severity": f.severity.value, "line": f.line,
                      "title": _meta(_defang(f.title), 120), "evidence": _meta(_defang(f.evidence), 300),
                      "data_begin": data_begin, "data_end": data_end}
            human = _content_text(self.verifier_prompt.format_messages(**inputs)[-1].content)
            if human.count(data_begin) != 1 or human.count(data_end) != 1 or human.index(data_begin) > human.index(data_end):
                logger.error("verify prompt boundary check failed", filename=_meta(filename))
                kept.append(f)
                continue
            calls += 1
            try:
                message = await self.verify_chain.ainvoke(inputs)
            except Exception as e:
                logger.warning("verify call failed, keeping the finding", filename=_meta(filename), error=type(e).__name__)
                kept.append(f)
                continue
            usage = getattr(message, "usage_metadata", None) or {}
            tokens_in += int(usage.get("input_tokens") or 0)
            tokens_out += int(usage.get("output_tokens") or 0)
            verdict = parse_verdict(_content_text(message.content))
            if verdict is None:
                logger.warning("verify verdict unreadable, keeping the finding", filename=_meta(filename))
                kept.append(f)
                continue
            if not verdict.confirmed:
                if verdict.confidence < self.settings.MIN_FINDING_CONFIDENCE:
                    logger.info("verifier unsure, keeping the finding", filename=_meta(filename), line=f.line, confidence=verdict.confidence)
                    kept.append(f)
                    continue
                refuted += 1
                logger.info("finding refuted by the verify pass", filename=_meta(filename), line=f.line, reason=verdict.reason[:200])
                continue
            severity = f.severity if SEVERITY_ORDER[f.severity] >= SEVERITY_ORDER[verdict.severity] else verdict.severity
            kept.append(f.model_copy(update={"severity": severity}))
        kept.sort(key=lambda x: (SEVERITY_ORDER[x.severity], x.line))
        summary = review.summary
        if refuted and not kept:
            summary = "Nothing survived verification for this file."
        elif refuted:
            note = f" ({refuted} finding{'s' if refuted != 1 else ''} did not survive verification and {'are' if refuted != 1 else 'is'} not shown.)"
            summary = (summary or "")[: 500 - len(note)].rstrip() + note
        return AnnotatedFileReview(findings=kept, summary=summary), refuted, calls, tokens_in, tokens_out

    async def review_file(self, filename: str, language: str, status: str, patch: str) -> FileReviewResult:
        started = time.perf_counter()
        # Redaction and defanging scan attacker-authored text with regexes; they run in a
        # worker thread so a pathological patch cannot stall the webhook and the dashboard.
        patch = await asyncio.to_thread(redact_text, patch or "")  # idempotent; the runner already redacted
        code_diff = await asyncio.to_thread(_defang, patch)
        data_begin, data_end = delimiters(secrets.token_hex(8))
        inputs = {"filename": _meta(filename), "language": _meta(language, 40), "status": _meta(status, 40),
                  "code_diff": code_diff, "data_begin": data_begin, "data_end": data_end}
        rendered = "\n".join(_content_text(m.content) for m in self.prompt.format_messages(**inputs))
        human = _content_text(self.prompt.format_messages(**inputs)[-1].content)
        if human.count(data_begin) != 1 or human.count(data_end) != 1 or human.index(data_begin) > human.index(data_end):
            logger.error("prompt boundary check failed", filename=_meta(filename))
            return FileReviewResult(filename, language, status, AnnotatedFileReview(findings=[], summary="Review skipped: prompt boundary check failed."),
                                    parse_ok=False, duration_seconds=time.perf_counter() - started, error="PromptBoundaryError")
        if self.settings.LOG_PROMPTS:
            logger.info("prompt", filename=filename, prompt=rendered)
        try:
            message = await self.chain.ainvoke(inputs)
        except Exception as e:
            logger.error("model call failed", filename=filename, error=type(e).__name__)
            return FileReviewResult(filename, language, status, AnnotatedFileReview(findings=[], summary="Model call failed."),
                                    parse_ok=False, duration_seconds=time.perf_counter() - started, error=type(e).__name__)
        text = _content_text(message.content)
        if self.settings.LOG_PROMPTS:
            logger.info("model output", filename=filename, output=redact_text(text)[:4000])
        first, ok = parse_file_review(text)
        first, dropped = postprocess(first, patch, self.settings.MIN_FINDING_CONFIDENCE, filename=filename,
                                     context_policy=self.settings.CONTEXT_LINE_FINDINGS,
                                     context_min_confidence=self.settings.CONTEXT_LINE_MIN_CONFIDENCE)
        review = annotate(first, self.model_name)
        usage = getattr(message, "usage_metadata", None) or {}
        result = FileReviewResult(
            filename=filename, language=language, status=status, review=review, dropped=dropped, parse_ok=ok,
            prompt_tokens=int(usage.get("input_tokens") or 0), output_tokens=int(usage.get("output_tokens") or 0),
            patch=patch,
        )
        if self.cross_inline:
            await self.cross_examine_file(result)
        if self.verify_enabled and result.review.findings:
            result.review, result.refuted, result.verify_calls, v_in, v_out = await self._verify(
                result.review, patch, filename, language)
            result.prompt_tokens += v_in
            result.output_tokens += v_out
        result.duration_seconds = time.perf_counter() - started
        return result
