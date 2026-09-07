"""One review job, end to end: fetch, filter, redact, review, render, post, persist."""

import asyncio
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.ext.asyncio import async_sessionmaker

from config.logging import get_logger
from config.settings import Settings
from database.repositories.review_repository import ReviewRepository
from database.repositories.webhook_repository import WebhookRepository
from services.ai_reviewer import FileReviewer, FileReviewResult
from services.comment_renderer import render_review, sanitise
from services.github_app_auth import InstallationTokenProvider
from services.github_client import GitHubClient
from services.redaction import is_excluded_path, redact
from services.review_queue import ReviewJob
from services.review_workflow import ReviewWorkflow, risk_score, totals_for
from utils.helpers import get_file_language, get_utc_timestamp

logger = get_logger(__name__)

SKIP_LANGUAGES = {"unknown", "markdown", "text", "rst"}
SKIP_DIRS = ("node_modules/", "vendor/", "dist/", "build/", ".next/", "__pycache__/")
LOCK_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock", "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock"}
BYTES_PER_TOKEN = 2.8          # conservative for code
PROMPT_OVERHEAD_TOKENS = 1400  # system prompt, schema and framing: measured up to 1206 on 2026-09-06
                               # for the 699-word prompt (scripts/prompt_overhead.py), with headroom
CLEANUP_SECONDS = 15
PARTIAL_HEAD_CHECK_SECONDS = 5   # a review cut short checks the head once more, briefly,
PARTIAL_POST_SECONDS = 20        # and posts what it has inside the queue's grace period
TIMEOUT_MARGIN_SECONDS = 60      # the runner's own deadline sits this far inside the queue's ceiling


class Superseded(Exception):
    """The PR head moved while this job was running, or this head was already
    reviewed; nothing is posted and the job ends as 'superseded'."""


class ReviewCutShort(Exception):
    """The review ran out of its own time budget. What finished was posted and
    the row written before this is raised (recorded says whether that write
    happened), so the queue reports the job as not completed without anything
    being written twice."""

    def __init__(self, message: str, recorded: bool):
        super().__init__(message)
        self.recorded = recorded


def review_budget(settings: Settings, files: int, elapsed: float) -> float:
    """Seconds the workflow may take: the file count times REVIEW_SECONDS_PER_FILE,
    never more than REVIEW_TIMEOUT_SECONDS, less what setup already spent and a
    margin so this deadline fires before the queue's ceiling does. A two-file
    pull request stops holding the queue for an hour; a twenty-five-file one
    keeps the ceiling, since the product exceeds it."""
    ceiling = float(settings.REVIEW_TIMEOUT_SECONDS)
    per_file = settings.REVIEW_SECONDS_PER_FILE
    total = min(ceiling, per_file * files) if per_file > 0 and files > 0 else ceiling
    return max(1.0, total - elapsed - TIMEOUT_MARGIN_SECONDS)


async def _post_failure_note(client: GitHubClient, job: ReviewJob, head_sha: str, elapsed: float, error_name: str) -> None:
    """One line on the pull request when a review failed before anything was
    posted, so silence cannot read as approval. Bounded, and a failure to post
    it is logged and swallowed: it is the last thing tried, not a second
    reason to fail. The exception's name is all it carries; the message stays
    in the dashboard."""
    body = ("## ReviewBot review\n\n"
            f"ReviewBot could not complete this review ({error_name} after {elapsed:.0f} s). "
            "Nothing was reviewed; the dashboard's review page has the reason.")
    try:
        await asyncio.wait_for(asyncio.shield(client.create_pull_review(job.repo, job.pr_number, head_sha, body, [])),
                               timeout=PARTIAL_POST_SECONDS)
    except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
        logger.warning("could not leave a note about the failed review", repo=job.repo, pr=job.pr_number, error=type(e).__name__)


def _how_far(where: Dict[str, Any]) -> str:
    return f" at {where['done']} of {where['total']} files in the {where['phase']} phase" if where.get("total") else ""


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


@dataclass
class Posted:
    comment_url: Optional[str]
    findings_total: int


def _finding_rows(succeeded: List[FileReviewResult]) -> List[Dict[str, Any]]:
    return [
        {"path": r.filename, "line": f.line, "category": f.category.value, "severity": f.severity.value,
         "source_model": getattr(f, "source_model", None) or None, "cross_verdict": getattr(f, "cross_verdict", None),
         "cross_reason": getattr(f, "cross_reason", "") or None,
         "title": f.title, "evidence": f.evidence, "recommendation": f.recommendation, "confidence": f.confidence}
        for r in succeeded for f in r.review.findings
    ]


async def _post_and_record(deps: RunnerDeps, client: GitHubClient, job: ReviewJob, review_id: str, *, head_sha: str,
                           succeeded: List[FileReviewResult], errored: List[FileReviewResult],
                           skipped: List[Tuple[str, str]], redaction_total: int, totals: Dict[str, int],
                           pr_title: str, files_total: int, started: float, status: str,
                           error_message: Optional[str], cut_short: str = "", post: bool = True,
                           post_seconds: Optional[float] = None) -> Posted:
    """Render what was reviewed, post it, and write the review row, its
    findings and the delivery row: the one path a finished review ends on,
    whatever its status. A review cut short passes post_seconds, since it
    runs inside a cancel with the queue's grace period as its whole budget,
    and post=False when the head has moved, so the row still gets its findings
    but nothing goes to a stale commit."""
    settings = deps.settings
    rendered = render_review(succeeded, model=settings.OLLAMA_MODEL, skipped=skipped, is_fork=job.is_fork,
                             fork_repo=job.fork_repo, max_inline=settings.MAX_INLINE_COMMENTS,
                             redaction_total=redaction_total, files_errored=len(errored),
                             cross_model=settings.CROSS_EXAMINE_MODEL or None,
                             cross_added=totals.get("cross_added", 0), cross_refuted=totals.get("cross_refuted", 0),
                             cut_short=cut_short)
    comment_url = None
    if post:
        call = client.create_pull_review(job.repo, job.pr_number, head_sha, rendered.body, rendered.comments)
        posted = await call if post_seconds is None else await asyncio.wait_for(asyncio.shield(call), timeout=post_seconds)
        comment_url = posted.get("html_url")
        # The review is live on GitHub now: record its URL before anything else can
        # interrupt us, and shield the writes so a cancel arriving here cannot leave
        # a posted review recorded as anything but completed.
        async def _record_url() -> None:
            async with deps.session_factory() as session:
                await ReviewRepository(session).update(review_id, {"comment_url": comment_url})
        await asyncio.wait_for(asyncio.shield(_record_url()), timeout=CLEANUP_SECONDS)
    duration = time.perf_counter() - started
    await asyncio.wait_for(asyncio.shield(_finish(deps, review_id, job.delivery_id, {
        "status": status, "head_sha": head_sha, "pr_title": pr_title,
        "files_total": files_total, "files_reviewed": len(succeeded), "files_skipped": len(skipped),
        "skipped": [{"path": p, "reason": r} for p, r in skipped],
        "findings_count": rendered.findings_total, "severity_counts": rendered.counts_by_severity,
        "findings_dropped": totals.get("dropped", 0), "redactions": redaction_total,
        "cross_added": totals.get("cross_added", 0), "cross_refuted": totals.get("cross_refuted", 0),
        "prompt_tokens": totals.get("prompt_tokens", 0), "output_tokens": totals.get("output_tokens", 0),
        "duration_seconds": duration, "comment_url": comment_url, "completed_at": get_utc_timestamp(),
        "summary": rendered.body[:6000] if comment_url else None, "error_message": error_message,
    }, status, findings=_finding_rows(succeeded))), timeout=CLEANUP_SECONDS)
    return Posted(comment_url, rendered.findings_total)


async def _post_cut_short(deps: RunnerDeps, client: GitHubClient, job: ReviewJob, review_id: str, *, head_sha: str,
                          done: "OrderedDict[str, FileReviewResult]", files: List[Dict[str, Any]],
                          skipped: List[Tuple[str, str]], redaction_total: int, pr: Dict[str, Any],
                          raw_files: List[Dict[str, Any]], started: float, where: Dict[str, Any], message: str) -> bool:
    """A review the queue's ceiling stopped: post the files that finished,
    list the rest under Not reviewed, and record the row with its findings.
    Every wait is bounded; the whole thing has the queue's grace period.
    True when the row was written. False sends the caller to the plain
    status-and-message record, which is what happened before this existed."""
    results = list(done.values())
    succeeded = [r for r in results if r.parse_ok and not r.error]
    errored = [r for r in results if not (r.parse_ok and not r.error)]
    skipped = list(skipped)
    for r in errored:
        skipped.append((r.filename, f"the model did not return a usable review ({r.error or 'unreadable reply'})"))
    for f in files:
        if f["filename"] not in done:
            skipped.append((f["filename"], "not reached before the review's time ran out"))
    elapsed = time.perf_counter() - started
    if where.get("phase") == "cross-examine":
        cut_short = (f"All {len(files)} files were reviewed; the cross-examiner reached {where.get('done', 0)} of them "
                     f"before time ran out after {elapsed:.0f} s.")
    elif results:
        cut_short = (f"This review ran out of time after {elapsed:.0f} s: {len(results)} of {len(files)} files were "
                     f"reviewed; the rest are listed under Not reviewed.")
    else:
        cut_short = f"This review ran out of time after {elapsed:.0f} s before finishing a file."
    try:
        latest = await asyncio.wait_for(asyncio.shield(client.get_pull(job.repo, job.pr_number)), timeout=PARTIAL_HEAD_CHECK_SECONDS)
        current = (latest.get("head", {}).get("sha") or head_sha) == head_sha
        if not current:
            logger.info("head moved while the review was being cut short; recording it without posting", repo=job.repo, pr=job.pr_number)
    except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
        logger.warning("could not check the head before posting a review cut short; recording it without posting",
                       repo=job.repo, pr=job.pr_number, error=type(e).__name__)
        current = False
    try:
        posted = await _post_and_record(deps, client, job, review_id, head_sha=head_sha, succeeded=succeeded, errored=errored,
                                        skipped=skipped, redaction_total=redaction_total, totals=totals_for(results),
                                        pr_title=sanitise(redact(pr.get("title") or "")[0], 200), files_total=len(raw_files),
                                        started=started, status="timed_out", error_message=message, cut_short=cut_short,
                                        post=current, post_seconds=PARTIAL_POST_SECONDS)
    except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
        logger.warning("could not post or record the review cut short", repo=job.repo, pr=job.pr_number, error=type(e).__name__)
        return False
    logger.info("review cut short posted", repo=job.repo, pr=job.pr_number, files=len(succeeded), of=len(files),
                findings=posted.findings_total, seconds=round(elapsed, 1), url=posted.comment_url)
    return True


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
    where: Dict[str, Any] = {}  # the last progress report, so a review cut short says how far it got
    done: "OrderedDict[str, FileReviewResult]" = OrderedDict()  # every file result so far, keyed by file, cross-examined ones overwriting
    # Bound before the try so the handler at the end can see them whenever the cancel lands.
    head_sha = job.head_sha
    pr: Dict[str, Any] = {}
    raw_files: List[Dict[str, Any]] = []
    files: List[Dict[str, Any]] = []
    skipped: List[Tuple[str, str]] = []
    redaction_total = 0
    attempted_post = False  # once a review may be on GitHub, a failure gets no second post
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

        async def _progress(phase: str, done: int, total: int, current: str) -> None:
            # one small write per file so the dashboard can show where the review is up to
            where.update(phase=phase, done=done, total=total)
            async with deps.session_factory() as session:
                await ReviewRepository(session).update(review_id, {
                    "progress_phase": phase, "progress_done": done, "progress_total": total,
                    "progress_file": current[:512] or None})

        workflow = ReviewWorkflow(FileReviewer(deps.llm, settings, cross_llm=deps.cross_llm), on_progress=_progress,
                                  on_result=lambda result: done.__setitem__(result.filename, result))
        budget = review_budget(settings, len(files), time.perf_counter() - started)
        try:
            state = await asyncio.wait_for(workflow.run(job.repo, job.pr_number, head_sha, files), timeout=budget)
        except asyncio.TimeoutError:
            # wait_for has cancelled the workflow and waited for it, so `done` is settled
            message = f"review timed out after {time.perf_counter() - started:.0f}s (budget of {budget:.0f}s){_how_far(where)}"
            recorded = await _post_cut_short(deps, client, job, review_id, head_sha=head_sha, done=done, files=files,
                                             skipped=skipped, redaction_total=redaction_total, pr=pr, raw_files=raw_files,
                                             started=started, where=where, message=message)
            raise ReviewCutShort(message, recorded)
        results = state.get("results", [])
        totals = state.get("totals", {})
        succeeded = [r for r in results if r.parse_ok and not r.error]
        errored = [r for r in results if not (r.parse_ok and not r.error)]
        for r in errored:
            skipped.append((r.filename, f"the model did not return a usable review ({r.error or 'unreadable reply'})"))

        latest = await client.get_pull(job.repo, job.pr_number)
        if (latest.get("head", {}).get("sha") or head_sha) != head_sha:
            raise Superseded("head moved while the review was running; the newer push will be reviewed")

        all_failed = bool(results) and not succeeded
        attempted_post = True
        posted = await _post_and_record(deps, client, job, review_id, head_sha=head_sha, succeeded=succeeded,
                                        errored=errored, skipped=skipped, redaction_total=redaction_total, totals=totals,
                                        pr_title=sanitise(redact(pr.get("title") or "")[0], 200), files_total=len(raw_files),
                                        started=started, status="failed" if all_failed else "completed",
                                        error_message="the model failed on every file" if all_failed else None)
        logger.info("review posted", repo=job.repo, pr=job.pr_number, findings=posted.findings_total,
                    files=len(succeeded), errored=len(errored), seconds=round(time.perf_counter() - started, 1),
                    url=posted.comment_url)
        return ReviewOutcome(review_id, posted.findings_total, len(succeeded), len(skipped), posted.comment_url)
    except BaseException as e:
        elapsed = time.perf_counter() - started
        recorded = False
        if isinstance(e, ReviewCutShort):
            status, message, recorded = "timed_out", str(e), e.recorded
        elif isinstance(e, asyncio.CancelledError):
            reason = job.cancel_reason or "superseded"
            status = {"timeout": "timed_out", "shutdown": "interrupted"}.get(reason, "superseded")
            message = f"review {status.replace('_', ' ')} after {elapsed:.0f}s ({reason}){_how_far(where)}"
            if reason == "timeout" and files:
                # the ceiling, not a newer push or a shutdown: what finished is worth posting
                recorded = await _post_cut_short(deps, client, job, review_id, head_sha=head_sha, done=done, files=files,
                                                 skipped=skipped, redaction_total=redaction_total, pr=pr, raw_files=raw_files,
                                                 started=started, where=where, message=message)
        elif isinstance(e, Superseded):
            status, message = "superseded", str(e)
        else:
            status = "failed"
            message = sanitise(redact(f"{type(e).__name__}: {e}")[0], 500)
            if not attempted_post:
                await _post_failure_note(client, job, head_sha, elapsed, type(e).__name__)
        if not recorded and not (isinstance(e, Superseded) and "already reviewed" in str(e)):
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
