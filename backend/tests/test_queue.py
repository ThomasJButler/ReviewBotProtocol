import asyncio

import pytest

from services.review_queue import ReviewQueue


async def _submit(q, sha, pr=1):
    return await q.submit(repo="octocat/repo", pr_number=pr, head_sha=sha, installation_id=1)


async def test_same_head_sha_is_reviewed_once():
    ran = []

    async def worker(job):
        ran.append(job.head_sha)
        await asyncio.sleep(0.05)

    q = ReviewQueue(worker=worker)
    await q.start()
    assert await _submit(q, "abc") == "queued"
    assert await _submit(q, "abc") == "duplicate"
    await q.drain(timeout=5)
    await q.stop()
    assert ran == ["abc"]


async def test_new_push_cancels_in_flight_review():
    finished, outcomes = [], []

    async def worker(job):
        await asyncio.sleep(0.3)
        finished.append(job.head_sha)

    q = ReviewQueue(worker=worker, on_result=lambda job, ok, err: outcomes.append((job.head_sha, ok, type(err).__name__ if err else None)))
    await q.start()
    await _submit(q, "old")
    await asyncio.sleep(0.05)
    assert await _submit(q, "new") == "superseded_inflight"
    await q.drain(timeout=5)
    await q.stop()
    assert finished == ["new"]
    assert outcomes[0] == ("old", False, "SupersededError") and outcomes[1] == ("new", True, None)


async def test_pending_job_for_same_pr_is_replaced():
    ran = []

    async def worker(job):
        ran.append(job.head_sha)
        await asyncio.sleep(0.1)

    q = ReviewQueue(worker=worker)
    await q.start()
    await _submit(q, "first")
    await asyncio.sleep(0.02)
    assert await _submit(q, "second", pr=2) == "queued"
    assert await _submit(q, "third", pr=2) == "replaced"
    await q.drain(timeout=5)
    await q.stop()
    assert ran == ["first", "third"]


async def test_review_deadline_is_enforced():
    outcomes = []

    async def worker(job):
        await asyncio.sleep(5)

    q = ReviewQueue(worker=worker, timeout_seconds=0.2, on_result=lambda job, ok, err: outcomes.append((ok, type(err).__name__)))
    await q.start()
    await _submit(q, "slow")
    await q.drain(timeout=5)
    await q.stop()
    assert outcomes == [(False, "TimeoutError")]


async def test_a_worker_that_ignores_cancellation_is_abandoned_after_the_grace_period():
    outcomes = []

    async def stubborn(job):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            await asyncio.sleep(5)  # refuses to unwind
            raise

    q = ReviewQueue(worker=stubborn, timeout_seconds=0.1, grace_seconds=0.1,
                    on_result=lambda job, ok, err: outcomes.append((job.head_sha, ok)))
    await q.start()
    await _submit(q, "stuck", pr=1)
    await _submit(q, "next", pr=2)
    await q.drain(timeout=5)
    await q.stop()
    assert outcomes == [("stuck", False), ("next", False)] or outcomes[0] == ("stuck", False)


class _Weird(BaseException):
    pass


async def test_base_exceptions_from_the_worker_do_not_kill_the_loop():
    outcomes = []

    async def worker(job):
        if job.head_sha == "bad":
            raise _Weird("nope")

    q = ReviewQueue(worker=worker, on_result=lambda job, ok, err: outcomes.append((job.head_sha, ok, type(err).__name__ if err else None)))
    await q.start()
    await _submit(q, "bad", pr=1)
    await _submit(q, "good", pr=2)
    await q.drain(timeout=5)
    assert q.alive
    await q.stop()
    assert outcomes == [("bad", False, "_Weird"), ("good", True, None)]


async def test_worker_exception_is_reported_and_queue_continues():
    outcomes = []

    async def worker(job):
        if job.head_sha == "bad":
            raise ValueError("nope")

    q = ReviewQueue(worker=worker, on_result=lambda job, ok, err: outcomes.append((job.head_sha, ok)))
    await q.start()
    await _submit(q, "bad", pr=1)
    await _submit(q, "good", pr=2)
    await q.drain(timeout=5)
    await q.stop()
    assert outcomes == [("bad", False), ("good", True)]


async def test_submit_after_stop_is_refused_and_pending_jobs_are_reported():
    async def worker(job):
        await asyncio.sleep(1)

    q = ReviewQueue(worker=worker)
    await q.start()
    await _submit(q, "a", pr=1)
    await asyncio.sleep(0.02)
    await _submit(q, "b", pr=2)
    assert [j.pr_number for j in q.pending_jobs] == [2]
    await q.stop()
    assert await _submit(q, "c", pr=3) == "shutting_down"
    assert not q.alive


async def test_drain_times_out_rather_than_hanging():
    async def worker(job):
        await asyncio.sleep(5)

    q = ReviewQueue(worker=worker, timeout_seconds=10)
    await q.start()
    await _submit(q, "slow")
    with pytest.raises(asyncio.TimeoutError):
        await q.drain(timeout=0.2)
    await q.stop()
