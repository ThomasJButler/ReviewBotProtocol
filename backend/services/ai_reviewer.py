"""One structured model call per file, then post-processing against the diff.

The chain is prompt | model bound to the JSON schema. The reply is parsed
leniently (a model that adds a fence or an extra field does not lose the
whole review), validated against the schema, and then every finding is
checked against the patch: the quoted evidence must actually be in the diff,
the line must be a line a comment can attach to, and confidence must clear
the floor. Findings that fail are dropped, not posted."""

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
from services.prompts import MARK_BEGIN, MARK_END, delimiters, review_prompt, verify_prompt
from services.redaction import redact_text
from services.schemas import SEVERITY_ORDER, FileReview, Finding, Verdict, output_schema, verdict_schema

logger = get_logger(__name__)
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_MARKER = re.compile(rf"<*\s*(?:{MARK_BEGIN}|{MARK_END})[A-Za-z0-9_]*\s*>*")


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
    review: FileReview
    dropped: int = 0
    parse_ok: bool = True
    prompt_tokens: int = 0
    output_tokens: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    refuted: int = 0        # findings the verify pass rejected
    verify_calls: int = 0   # verify calls made (one per finding that reached the pass)
    redactions: Dict[str, int] = field(default_factory=dict)


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
                 verifier_prompt=verify_prompt, verify: Optional[bool] = None):
        self.settings = settings
        self.prompt = prompt
        self.verifier_prompt = verifier_prompt
        self.verify_enabled = settings.VERIFY_FINDINGS if verify is None else verify
        self.verify_budget = settings.MAX_VERIFY_CALLS_PER_REVIEW  # shared across every file of one review
        self.chain = prompt | llm.bind(format=output_schema())
        self.verify_chain = verifier_prompt | llm.bind(format=verdict_schema())

    async def _verify(self, review: FileReview, patch: str, filename: str, language: str) -> Tuple[FileReview, int, int, int, int]:
        """Run every finding past the verifier. Returns the surviving review,
        how many were refuted, how many calls were made, and the tokens used.
        Severity can only go down. An unreadable or failed verdict keeps the
        finding and is logged."""
        kept: List[Finding] = []
        refuted = calls = tokens_in = tokens_out = 0
        for f in review.findings:
            if self.verify_budget <= 0:
                logger.warning("verify budget exhausted for this review, keeping the remaining findings unverified", filename=_meta(filename))
                kept.append(f)
                continue
            self.verify_budget -= 1
            data_begin, data_end = delimiters(secrets.token_hex(8))
            inputs = {"filename": _meta(filename), "language": _meta(language, 40), "code_diff": _defang(patch or ""),
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
        return FileReview(findings=kept, summary=summary), refuted, calls, tokens_in, tokens_out

    async def review_file(self, filename: str, language: str, status: str, patch: str) -> FileReviewResult:
        started = time.perf_counter()
        patch = redact_text(patch or "")  # idempotent; the runner already redacted, unit callers may not have
        data_begin, data_end = delimiters(secrets.token_hex(8))
        inputs = {"filename": _meta(filename), "language": _meta(language, 40), "status": _meta(status, 40),
                  "code_diff": _defang(patch or ""), "data_begin": data_begin, "data_end": data_end}
        rendered = "\n".join(_content_text(m.content) for m in self.prompt.format_messages(**inputs))
        human = _content_text(self.prompt.format_messages(**inputs)[-1].content)
        if human.count(data_begin) != 1 or human.count(data_end) != 1 or human.index(data_begin) > human.index(data_end):
            logger.error("prompt boundary check failed", filename=_meta(filename))
            return FileReviewResult(filename, language, status, FileReview(findings=[], summary="Review skipped: prompt boundary check failed."),
                                    parse_ok=False, duration_seconds=time.perf_counter() - started, error="PromptBoundaryError")
        if self.settings.LOG_PROMPTS:
            logger.info("prompt", filename=filename, prompt=rendered)
        try:
            message = await self.chain.ainvoke(inputs)
        except Exception as e:
            logger.error("model call failed", filename=filename, error=type(e).__name__)
            return FileReviewResult(filename, language, status, FileReview(findings=[], summary="Model call failed."),
                                    parse_ok=False, duration_seconds=time.perf_counter() - started, error=type(e).__name__)
        text = _content_text(message.content)
        if self.settings.LOG_PROMPTS:
            logger.info("model output", filename=filename, output=redact_text(text)[:4000])
        review, ok = parse_file_review(text)
        review, dropped = postprocess(review, patch, self.settings.MIN_FINDING_CONFIDENCE)
        usage = getattr(message, "usage_metadata", None) or {}
        prompt_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        refuted = verify_calls = 0
        if self.verify_enabled and review.findings:
            review, refuted, verify_calls, v_in, v_out = await self._verify(review, patch, filename, language)
            prompt_tokens += v_in
            output_tokens += v_out
        return FileReviewResult(
            filename=filename, language=language, status=status, review=review, dropped=dropped, parse_ok=ok,
            prompt_tokens=prompt_tokens, output_tokens=output_tokens,
            duration_seconds=time.perf_counter() - started, refuted=refuted, verify_calls=verify_calls,
        )
