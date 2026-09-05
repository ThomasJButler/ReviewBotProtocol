"""One review job, end to end: fetch, filter, redact, review, render, post, persist."""

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.ext.asyncio import async_sessionmaker

from config.logging import get_logger
from config.settings import Settings
from database.repositories.review_repository import ReviewRepository
from database.repositories.webhook_repository import WebhookRepository
from services.ai_reviewer import FileReviewer
from services.comment_renderer import render_review, sanitise
from services.github_app_auth import InstallationTokenProvider
from services.github_client import GitHubClient
from services.redaction import is_excluded_path, redact
from services.review_queue import ReviewJob
from services.review_workflow import ReviewWorkflow, risk_score
from utils.helpers import get_file_language, get_utc_timestamp

logger = get_logger(__name__)

SKIP_LANGUAGES = {"unknown", "markdown", "text", "rst"}
SKIP_DIRS = ("node_modules/", "vendor/", "dist/", "build/", ".next/", "__pycache__/")
LOCK_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock", "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock"}
BYTES_PER_TOKEN = 2.8          # conservative for code
PROMPT_OVERHEAD_TOKENS = 1400  # system prompt, schema and framing: measured up to 1206 on 2026-09-06
                               # for the 699-word prompt (scripts/prompt_overhead.py), with headroom
CLEANUP_SECONDS = 15


class Superseded(Exception):
    """The PR head moved while this job was running, or this head was already
    reviewed; nothing is posted and the job ends as 'superseded'."""


@dataclass
class RunnerDeps:
    settings: Settings
    llm: BaseChatModel
    session_factory: async_sessionmaker
    http: Optional[httpx.AsyncClient] = None  # injected in tests so respx can serve the fake GitHub
    cross_llm: Optional[BaseChatModel] = None  # the cross-examining model, when configured


@dataclass
class ReviewOutcome:
    review_id: str
    findings: int
    files_reviewed: int
    files_skipped: int
    comment_url: Optional[str]


def _fits_context(patch: str, settings: Settings) -> bool:
    tokens = len(patch.encode("utf-8")) / BYTES_PER_TOKEN
    return tokens + PROMPT_OVERHEAD_TOKENS + settings.OLLAMA_NUM_PREDICT <= settings.OLLAMA_NUM_CTX


def _skip_reason(f: Dict[str, Any], settings: Settings) -> Optional[str]:
    name = f.get("filename", "")
    base = name.rsplit("/", 1)[-1]
    status = f.get("status")
    if status == "removed":
        return "deleted file"
    if not f.get("patch"):
        if status in ("renamed", "copied"):
            return "renamed or copied with no content change"
        if status == "unchanged":
            return "unchanged in this pull request"
        return "no text diff available (binary or too large for GitHub)"
    if is_excluded_path(name):
        return "secret-bearing file, never sent to the model"
    if base in LOCK_FILES or any(name.startswith(d) or f"/{d}" in name for d in SKIP_DIRS) or base.endswith(".min.js"):
        return "generated or vendored"
    if len(f["patch"].encode("utf-8")) > settings.MAX_PATCH_BYTES:
        return f"patch larger than {settings.MAX_PATCH_BYTES} bytes"
    if not _fits_context(f["patch"], settings):
        return "patch too large for the model's context window"
    if get_file_language(name) in SKIP_LANGUAGES:
        return "not code"
    return None


def select_files(raw_files: List[Dict[str, Any]], settings: Settings) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    """Eligibility first, then the riskiest eligible files up to the cap."""
    eligible: List[Dict[str, Any]] = []
    skipped: List[Tuple[str, str]] = []
    for f in raw_files:
        reason = _skip_reason(f, settings)
        if reason:
            skipped.append((f.get("filename", ""), reason))
        else:
            eligible.append(f)
    eligible.sort(key=lambda f: -risk_score(f.get("filename", ""), f.get("additions", 0)))
    selected = eligible[: settings.MAX_FILES_PER_REVIEW]
    for f in eligible[settings.MAX_FILES_PER_REVIEW:]:
        skipped.append((f.get("filename", ""), f"over the {settings.MAX_FILES_PER_REVIEW} file limit"))
    return selected, skipped


def prepare_files(selected: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    prepared = []
    redaction_total = 0
    for f in selected:
        text, counts = redact(f["patch"])
        redaction_total += sum(counts.values())
        prepared.append({
            "filename": f["filename"], "language": get_file_language(f["filename"]),
            "status": f.get("status", "modified"), "patch": text,
            "additions": f.get("additions", 0), "redactions": counts,
        })
    return prepared, redaction_total


async def _finish(deps: RunnerDeps, review_id: str, delivery_id: str, review_update: Dict[str, Any],
                  delivery_status: str, findings: Optional[List[Dict[str, Any]]] = None) -> None:
    """One transaction for the review row, its findings and the delivery row."""
    async with deps.session_factory() as session:
        repo_db = ReviewRepository(session)
        await repo_db.update(review_id, review_update, commit=False)
        if findings:
            await repo_db.add_findings(review_id, findings, commit=False)
        await WebhookRepository(session).mark(delivery_id, status=delivery_status, review_id=review_id, commit=False)
        await session.commit()


async def run_review(job: ReviewJob, deps: RunnerDeps) -> ReviewOutcome:
    settings = deps.settings
    review_id = str(uuid.uuid4())
    started = time.perf_counter()
    async with deps.session_factory() as session:
        repo_db = ReviewRepository(session)
        if await repo_db.completed_for(job.repo, job.pr_number, job.head_sha):
            await WebhookRepository(session).mark(job.delivery_id, status="duplicate")
            logger.info("head already reviewed, skipping", repo=job.repo, pr=job.pr_number, head=job.head_sha[:12])
            raise Superseded("this head was already reviewed")
        await repo_db.create({
            "id": review_id, "repository": job.repo, "pr_number": job.pr_number, "head_sha": job.head_sha,
            "is_fork": job.is_fork, "status": "running", "model": settings.OLLAMA_MODEL,
            "cross_model": settings.CROSS_EXAMINE_MODEL or None,
            "delivery_id": job.delivery_id or None, "started_at": get_utc_timestamp(),
        })
        await WebhookRepository(session).mark(job.delivery_id, status="running", review_id=review_id)

    provider = InstallationTokenProvider(settings.GITHUB_APP_ID, settings.GITHUB_PRIVATE_KEY, job.installation_id,
                                         base_url=settings.GITHUB_API_BASE_URL, http=deps.http, repository=job.repo)
    client = GitHubClient(provider, base_url=settings.GITHUB_API_BASE_URL, http=deps.http)
    try:
        pr = await client.get_pull(job.repo, job.pr_number)
        head_sha = pr.get("head", {}).get("sha") or job.head_sha
        if head_sha != job.head_sha:
            raise Superseded(f"head moved from {job.head_sha[:12]} to {head_sha[:12]} before the review started")
        raw_files, truncated = await client.list_pull_files(job.repo, job.pr_number)
        selected, skipped = select_files(raw_files, settings)
        if truncated:
            skipped.append(("(remaining files)", "the pull request has more files than this bot will fetch"))
        files, redaction_total = await asyncio.to_thread(prepare_files, selected)
        logger.info("review starting", repo=job.repo, pr=job.pr_number, files=len(files), skipped=len(skipped),
                    redactions=redaction_total, model=settings.OLLAMA_MODEL)

        workflow = ReviewWorkflow(FileReviewer(deps.llm, settings, cross_llm=deps.cross_llm))
        state = await workflow.run(job.repo, job.pr_number, head_sha, files)
        results = state.get("results", [])
        totals = state.get("totals", {})
        succeeded = [r for r in results if r.parse_ok and not r.error]
        errored = [r for r in results if not (r.parse_ok and not r.error)]
        for r in errored:
            skipped.append((r.filename, f"the model did not return a usable review ({r.error or 'unreadable reply'})"))

        latest = await client.get_pull(job.repo, job.pr_number)
        if (latest.get("head", {}).get("sha") or head_sha) != head_sha:
            raise Superseded("head moved while the review was running; the newer push will be reviewed")

        rendered = render_review(succeeded, model=settings.OLLAMA_MODEL, skipped=skipped, is_fork=job.is_fork,
                                 fork_repo=job.fork_repo, max_inline=settings.MAX_INLINE_COMMENTS,
                                 redaction_total=redaction_total, files_errored=len(errored),
                                 cross_model=settings.CROSS_EXAMINE_MODEL or None,
                                 cross_added=totals.get("cross_added", 0), cross_refuted=totals.get("cross_refuted", 0))
        posted = await client.create_pull_review(job.repo, job.pr_number, head_sha, rendered.body, rendered.comments)
        comment_url = posted.get("html_url")
        # The review is live on GitHub now: record its URL before anything else can
        # interrupt us, and shield the writes so a cancel arriving here cannot leave
        # a posted review recorded as anything but completed.
        async def _record_url() -> None:
            async with deps.session_factory() as session:
                await ReviewRepository(session).update(review_id, {"comment_url": comment_url})
        await asyncio.wait_for(asyncio.shield(_record_url()), timeout=CLEANUP_SECONDS)
        duration = time.perf_counter() - started
        all_failed = bool(results) and not succeeded

        await asyncio.wait_for(asyncio.shield(_finish(deps, review_id, job.delivery_id, {
            "status": "failed" if all_failed else "completed", "head_sha": head_sha,
            "pr_title": sanitise(redact(pr.get("title") or "")[0], 200),
            "files_total": len(raw_files), "files_reviewed": len(succeeded), "files_skipped": len(skipped),
            "skipped": [{"path": p, "reason": r} for p, r in skipped],
            "findings_count": rendered.findings_total, "severity_counts": rendered.counts_by_severity,
            "findings_dropped": totals.get("dropped", 0), "redactions": redaction_total,
            "cross_added": totals.get("cross_added", 0), "cross_refuted": totals.get("cross_refuted", 0),
            "prompt_tokens": totals.get("prompt_tokens", 0), "output_tokens": totals.get("output_tokens", 0),
            "duration_seconds": duration, "comment_url": comment_url, "completed_at": get_utc_timestamp(),
            "summary": rendered.body[:6000],
            "error_message": "the model failed on every file" if all_failed else None,
        }, "failed" if all_failed else "completed", findings=[
            {"path": r.filename, "line": f.line, "category": f.category.value, "severity": f.severity.value,
             "source_model": getattr(f, "source_model", None) or None, "cross_verdict": getattr(f, "cross_verdict", None),
             "cross_reason": getattr(f, "cross_reason", "") or None,
             "title": f.title, "evidence": f.evidence, "recommendation": f.recommendation, "confidence": f.confidence}
            for r in succeeded for f in r.review.findings
        ])), timeout=CLEANUP_SECONDS)
        logger.info("review posted", repo=job.repo, pr=job.pr_number, findings=rendered.findings_total,
                    files=len(succeeded), errored=len(errored), seconds=round(duration, 1), url=comment_url)
        return ReviewOutcome(review_id, rendered.findings_total, len(succeeded), len(skipped), comment_url)
    except BaseException as e:
        elapsed = time.perf_counter() - started
        if isinstance(e, asyncio.CancelledError):
            reason = job.cancel_reason or "superseded"
            status = {"timeout": "timed_out", "shutdown": "interrupted"}.get(reason, "superseded")
            message = f"review {status.replace('_', ' ')} after {elapsed:.0f}s ({reason})"
        elif isinstance(e, Superseded):
            status, message = "superseded", str(e)
        else:
            status = "failed"
            message = sanitise(redact(f"{type(e).__name__}: {e}")[0], 500)
        if not (isinstance(e, Superseded) and "already reviewed" in str(e)):
            try:
                await asyncio.wait_for(asyncio.shield(_finish(deps, review_id, job.delivery_id, {
                    "status": status, "error_message": message, "duration_seconds": elapsed,
                    "completed_at": get_utc_timestamp()}, status)), timeout=CLEANUP_SECONDS)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as cleanup_error:
                logger.error("could not record the review outcome", review_id=review_id, error=type(cleanup_error).__name__)
        if isinstance(e, Superseded):
            logger.info("review superseded", repo=job.repo, pr=job.pr_number, reason=str(e))
        raise
    finally:
        try:
            await asyncio.wait_for(asyncio.shield(client.aclose()), timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            pass
