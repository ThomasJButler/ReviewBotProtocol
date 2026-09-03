"""A single-worker review queue with dedupe, supersede and a hard deadline.

One review runs at a time, because one local model runs at a time. A job is
keyed by (repo, pr_number). A second webhook for the same PR and the same
head SHA is a duplicate and does nothing. A newer head SHA replaces a pending
job or cancels the one in flight. Every job runs under a deadline, and a
worker that will not stop after the deadline plus a grace period is abandoned
so the queue keeps moving. The loop survives anything a worker throws."""

import asyncio
import inspect
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from config.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReviewJob:
    repo: str
    pr_number: int
    head_sha: str
    installation_id: int
    delivery_id: str = ""
    is_fork: bool = False
    fork_repo: Optional[str] = None

    @property
    def key(self) -> Tuple[str, int]:
        return (self.repo, self.pr_number)


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

    async def submit(self, *, repo: str, pr_number: int, head_sha: str, installation_id: int,
                     delivery_id: str = "", is_fork: bool = False, fork_repo: Optional[str] = None) -> str:
        if self._stopping:
            return "shutting_down"
        if not self.alive:
            return "queue_dead"
        job = ReviewJob(repo, pr_number, head_sha, installation_id, delivery_id, is_fork, fork_repo)
        outcome = "queued"
        if self._current and self._current["job"].key == job.key:
            if self._current["job"].head_sha == job.head_sha:
                return "duplicate"
            self._current["superseded"] = True
            self._current["task"].cancel()
            outcome = "superseded_inflight"
        pending = self._pending.get(job.key)
        if pending is not None:
            if pending.head_sha == job.head_sha:
                return "duplicate"
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

    async def _run(self, job: ReviewJob) -> None:
        inner = asyncio.create_task(self._worker(job), name=f"review-worker-{job.repo}-{job.pr_number}")
        try:
            done, _ = await asyncio.wait({inner}, timeout=self._timeout)
            if inner in done:
                exc = inner.exception()
                if exc is None:
                    await self._report(job, True, None)
                else:
                    logger.error("review job failed", repo=job.repo, pr=job.pr_number, error=type(exc).__name__)
                    await self._report(job, False, exc)
                return
            # Deadline: cancel and give the worker a bounded time to unwind.
            inner.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(inner), timeout=self._grace)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                pass
            if not inner.done():
                logger.error("worker did not stop after the grace period; abandoning it", repo=job.repo, pr=job.pr_number)
            await self._report(job, False, asyncio.TimeoutError(f"review exceeded {self._timeout:.0f}s"))
        except asyncio.CancelledError:
            # Superseded or stopping: cancel the worker and let it unwind briefly.
            inner.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(inner), timeout=self._grace)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                pass
            await self._report(job, False, SupersededError("superseded by a newer push") if not self._stopping else asyncio.CancelledError("shutdown"))
            raise
        except BaseException as e:  # never let anything kill the loop silently
            logger.error("review runner raised", repo=job.repo, pr=job.pr_number, error=type(e).__name__)
            await self._report(job, False, e)
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                if not self._pending:
                    self._wakeup.clear()
                    await self._wakeup.wait()
                    continue
                _, job = self._pending.popitem(last=False)
                task = asyncio.create_task(self._run(job), name=f"review-{job.repo}-{job.pr_number}")
                self._current = {"job": job, "task": task, "superseded": False}
                try:
                    await task
                except asyncio.CancelledError:
                    if self._stopping or not self._current.get("superseded"):
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
        while self._pending or self._current is not None:
            if not self.alive:
                raise RuntimeError("review queue loop is not running")
            if timeout is not None and waited >= timeout:
                raise asyncio.TimeoutError("queue did not drain in time")
            await asyncio.sleep(0.02)
            waited += 0.02

    async def stop(self) -> None:
        self._stopping = True
        self._wakeup.set()
        if self._current:
            self._current["task"].cancel()
        if self._loop_task:
            self._loop_task.cancel()
            await asyncio.gather(self._loop_task, return_exceptions=True)
            self._loop_task = None
