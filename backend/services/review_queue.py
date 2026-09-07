"""A single-worker review queue with dedupe, supersede and a hard deadline.

One review runs at a time, because one local model runs at a time. A job is
keyed by (repo, pr_number). A second webhook for the same PR and the same
head SHA is a duplicate and does nothing. A newer head SHA replaces a pending
job or cancels the one in flight. Every job runs under a deadline; a worker
that will not stop after the deadline plus a grace period is set aside and
awaited before the next job starts, so two reviews never run at once. The
worker is told why it was cancelled through job.state["cancel_reason"]."""

import asyncio
import inspect
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple

from config.logging import get_logger

logger = get_logger(__name__)


def _older(incoming: "ReviewJob", held: "ReviewJob") -> bool:
    """Whether the incoming delivery describes an older state of the pull request
    than the job already held, by GitHub's own updated_at (ISO 8601 in UTC, so the
    strings order as the times do). Unknown on either side means not older: an old
    client or a test without the field keeps the plain newest-wins behaviour."""
    return bool(incoming.updated_at and held.updated_at and incoming.updated_at < held.updated_at)


@dataclass
class ReviewJob:
    repo: str
    pr_number: int
    head_sha: str
    installation_id: int
    delivery_id: str = ""
    is_fork: bool = False
    fork_repo: Optional[str] = None
    updated_at: str = ""  # the payload's pull_request.updated_at, so a replayed old delivery cannot cancel a newer job
    state: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def key(self) -> Tuple[str, int]:
        return (self.repo, self.pr_number)

    @property
    def cancel_reason(self) -> Optional[str]:
        return self.state.get("cancel_reason")


class SupersededError(asyncio.CancelledError):
    """The job was cancelled because a newer push arrived for the same PR."""


class ReviewQueue:
    def __init__(self, worker: Callable[[ReviewJob], Awaitable[Any]], timeout_seconds: float = 900.0,
                 on_result: Optional[Callable[[ReviewJob, bool, Optional[BaseException]], Any]] = None,
                 grace_seconds: float = 30.0):
        self._worker = worker
        self._timeout = timeout_seconds
        self._grace = grace_seconds
        self._on_result = on_result
        self._pending: "OrderedDict[Tuple[str, int], ReviewJob]" = OrderedDict()
        self._current: Optional[Dict[str, Any]] = None
        self._abandoned: Set[asyncio.Task] = set()
        self._wakeup = asyncio.Event()
        self._loop_task: Optional[asyncio.Task] = None
        self._stopping = False

    @property
    def depth(self) -> int:
        return len(self._pending)

    @property
    def current_job(self) -> Optional[ReviewJob]:
        return self._current["job"] if self._current else None

    @property
    def pending_jobs(self) -> List[ReviewJob]:
        return list(self._pending.values())

    @property
    def abandoned(self) -> int:
        self._abandoned = {t for t in self._abandoned if not t.done()}
        return len(self._abandoned)

    @property
    def alive(self) -> bool:
        return self._loop_task is not None and not self._loop_task.done()

    async def start(self) -> None:
        if self._loop_task is None or self._loop_task.done():
            self._stopping = False
            self._loop_task = asyncio.create_task(self._loop(), name="review-queue")
            self._loop_task.add_done_callback(self._loop_finished)

    def _loop_finished(self, task: asyncio.Task) -> None:
        if task.cancelled() or self._stopping:
            return
        logger.error("review queue loop died", error=type(task.exception()).__name__ if task.exception() else "unknown")

    def _cancel_current(self, reason: str) -> None:
        if self._current:
            self._current["job"].state["cancel_reason"] = reason
            self._current["reason"] = reason
            self._current["task"].cancel()

    async def submit(self, *, repo: str, pr_number: int, head_sha: str, installation_id: int,
                     delivery_id: str = "", is_fork: bool = False, fork_repo: Optional[str] = None,
                     updated_at: str = "") -> str:
        if self._stopping:
            return "shutting_down"
        if not self.alive:
            return "queue_dead"
        job = ReviewJob(repo, pr_number, head_sha, installation_id, delivery_id, is_fork, fork_repo, updated_at)
        outcome = "queued"
        if self._current and self._current["job"].key == job.key:
            if self._current["job"].head_sha == job.head_sha:
                return "duplicate"
            if _older(job, self._current["job"]):
                return "stale"  # a captured body replayed under a fresh id: it never cancels the newer review
            self._cancel_current("superseded")
            outcome = "superseded_inflight"
        pending = self._pending.get(job.key)
        if pending is not None:
            if pending.head_sha == job.head_sha and outcome == "queued":
                return "duplicate"
            if outcome == "queued" and _older(job, pending):
                return "stale"
            if outcome == "queued":
                outcome = "replaced"
        self._pending[job.key] = job
        self._wakeup.set()
        logger.info("review job submitted", repo=repo, pr=pr_number, head=head_sha[:12], outcome=outcome, depth=self.depth)
        return outcome

    async def _report(self, job: ReviewJob, ok: bool, err: Optional[BaseException]) -> None:
        if self._on_result is None:
            return
        try:
            res = self._on_result(job, ok, err)
            if inspect.isawaitable(res):
                await res
        except Exception as e:  # a reporting failure must not kill the worker
            logger.error("on_result failed", error=type(e).__name__)

    async def _unwind(self, inner: asyncio.Task) -> bool:
        """Cancel the worker and give it a bounded time to finish. True if it did."""
        inner.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(inner), timeout=self._grace)
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            pass
        return inner.done()

    async def _run(self, job: ReviewJob) -> None:
        inner = asyncio.create_task(self._worker(job), name=f"review-worker-{job.repo}-{job.pr_number}")
        try:
            done, _ = await asyncio.wait({inner}, timeout=self._timeout)
            if inner in done:
                if inner.cancelled():
                    await self._report(job, False, asyncio.CancelledError("the worker cancelled itself"))
                    return
                exc = inner.exception()
                if exc is None:
                    await self._report(job, True, None)
                else:
                    logger.error("review job failed", repo=job.repo, pr=job.pr_number, error=type(exc).__name__)
                    await self._report(job, False, exc)
                return
            job.state["cancel_reason"] = "timeout"
            if not await self._unwind(inner):
                logger.error("worker did not stop after the grace period; waiting for it before the next job",
                             repo=job.repo, pr=job.pr_number)
                self._abandoned.add(inner)
            await self._report(job, False, asyncio.TimeoutError(f"review exceeded {self._timeout:.0f}s"))
        except asyncio.CancelledError:
            reason = job.state.get("cancel_reason") or ("shutdown" if self._stopping else "superseded")
            job.state["cancel_reason"] = reason
            if not await self._unwind(inner):
                self._abandoned.add(inner)
            err = SupersededError("superseded by a newer push") if reason == "superseded" else asyncio.CancelledError(reason)
            await self._report(job, False, err)
            raise
        except BaseException as e:  # never let anything kill the loop silently
            logger.error("review runner raised", repo=job.repo, pr=job.pr_number, error=type(e).__name__)
            await self._report(job, False, e)
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise

    async def _wait_for_abandoned(self) -> None:
        live = [t for t in self._abandoned if not t.done()]
        if live:
            logger.warning("waiting for abandoned workers before starting the next review", count=len(live))
            await asyncio.gather(*live, return_exceptions=True)
        self._abandoned = set()

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                if not self._pending:
                    self._wakeup.clear()
                    await self._wakeup.wait()
                    continue
                await self._wait_for_abandoned()
                if self._stopping:
                    break
                _, job = self._pending.popitem(last=False)
                task = asyncio.create_task(self._run(job), name=f"review-{job.repo}-{job.pr_number}")
                self._current = {"job": job, "task": task, "reason": None}
                try:
                    await task
                except asyncio.CancelledError:
                    if self._stopping or not self._current or self._current.get("reason") is None:
                        raise
                finally:
                    self._current = None
            except asyncio.CancelledError:
                if self._stopping:
                    raise
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException as e:
                logger.error("review queue loop error, continuing", error=type(e).__name__)
                await asyncio.sleep(0.1)

    async def drain(self, timeout: Optional[float] = None) -> None:
        waited = 0.0
        while self._pending or self._current is not None or self.abandoned:
            if not self.alive:
                raise RuntimeError("review queue loop is not running")
            if timeout is not None and waited >= timeout:
                raise asyncio.TimeoutError("queue did not drain in time")
            await asyncio.sleep(0.02)
            waited += 0.02

    async def stop(self) -> None:
        self._stopping = True
        self._wakeup.set()
        self._cancel_current("shutdown")
        if self._loop_task:
            self._loop_task.cancel()
            await asyncio.gather(self._loop_task, return_exceptions=True)
            self._loop_task = None
        live = [t for t in self._abandoned if not t.done()]
        for t in live:
            t.cancel()
        if live:
            await asyncio.gather(*live, return_exceptions=True)
        self._abandoned = set()
