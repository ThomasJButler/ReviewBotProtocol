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
from config.settings import Settings
from services.diff import locate_evidence, locate_evidence_part, parse_patch
from services.prompts import MARK_BEGIN, MARK_END, cross_prompt, delimiters, review_prompt, verify_prompt
from services.redaction import redact_text
from services.schemas import (SEVERITY_ORDER, AnnotatedFileReview, CrossExamination, FileReview, Finding, ReviewedFinding,
                              Verdict, cross_schema, output_schema, verdict_schema)

logger = get_logger(__name__)
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
# Bounded, newline-free repeats on both sides: the engine tries at most 16 characters
# before the literal at any position, so a line of 32,000 '<' costs linear time, and a
# marker never swallows the line break before it (line numbers stay honest). Brackets
# beyond the bound are left behind on their own, which cannot rebuild a delimiter
# because the marker name itself is gone.
_MARKER = re.compile(rf"[<\t ]{{0,16}}(?:{MARK_BEGIN}|{MARK_END})[A-Za-z0-9_]{{0,64}}[\t >]{{0,16}}")


class PromptBoundaryError(RuntimeError):
    """The rendered prompt did not contain exactly one begin and one end delimiter."""


def _defang(text: str) -> str:
    """Anything in PR content that resembles a data delimiter, with any number
    of angle brackets and any nonce suffix, is rewritten to a bracket-free
    token. The replacement contains no angle brackets, so it cannot be
    reassembled into a delimiter by a second pass."""
    return _MARKER.sub("[data-marker]", text)


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


def postprocess(review: FileReview, patch: Optional[str], min_confidence: float) -> Tuple[FileReview, int]:
    parsed = parse_patch(patch)
    kept: List[Finding] = []
    seen = set()
    for f in review.findings:
        if f.confidence < min_confidence:
            continue
        located, part = locate_evidence_part(parsed, f.line, f.evidence)
        if located is None:
            continue
        key = (located, f.title.strip().lower())
        if key in seen:
            continue
        seen.add(key)
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
        additions, _ = postprocess(FileReview(findings=ce.additions, summary=""), patch, floor)
        seen = {(f.line, f.title.strip().lower()) for f in kept}
        added = 0
        for f in additions.findings:
            key = (f.line, f.title.strip().lower())
            if key in seen:
                continue
            if f.line in refuted_at:
                # "false positive" followed by the second model's own finding on the same line is a
                # correction of severity or wording, not a refutation: the first reviewer's finding
                # stands with its provenance, at the lowest severity anyone gave it
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
        first, dropped = postprocess(first, patch, self.settings.MIN_FINDING_CONFIDENCE)
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
