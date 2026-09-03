"""The review queue contract for Phase 4 step 4. Everything here is a strict
expected failure until services.review_queue exists."""

import asyncio

import pytest


@pytest.mark.xfail(strict=True, reason="Phase 4 step 4: services.review_queue does not exist yet")
async def test_same_head_sha_is_reviewed_once():
    from services.review_queue import ReviewQueue
    ran = []

    async def worker(job):
        ran.append(job.head_sha)
        await asyncio.sleep(0.05)

    q = ReviewQueue(worker=worker)
    await q.start()
    await q.submit(repo="octocat/repo", pr_number=1, head_sha="abc", installation_id=1)
    await q.submit(repo="octocat/repo", pr_number=1, head_sha="abc", installation_id=1)
    await q.drain()
    await q.stop()
    assert ran == ["abc"]


@pytest.mark.xfail(strict=True, reason="Phase 4 step 4: a newer push must cancel the in-flight review of the same PR")
async def test_new_push_cancels_in_flight_review():
    from services.review_queue import ReviewQueue
    finished = []

    async def worker(job):
        await asyncio.sleep(0.3)
        finished.append(job.head_sha)

    q = ReviewQueue(worker=worker)
    await q.start()
    await q.submit(repo="octocat/repo", pr_number=1, head_sha="old", installation_id=1)
    await asyncio.sleep(0.05)
    await q.submit(repo="octocat/repo", pr_number=1, head_sha="new", installation_id=1)
    await q.drain()
    await q.stop()
    assert finished == ["new"]


@pytest.mark.xfail(strict=True, reason="Phase 4 step 4: reviews must have a hard deadline")
async def test_review_deadline_is_enforced():
    from services.review_queue import ReviewQueue
    outcomes = []

    async def worker(job):
        await asyncio.sleep(5)

    q = ReviewQueue(worker=worker, timeout_seconds=0.2, on_result=lambda job, ok, err: outcomes.append((ok, type(err).__name__ if err else None)))
    await q.start()
    await q.submit(repo="octocat/repo", pr_number=1, head_sha="slow", installation_id=1)
    await q.drain()
    await q.stop()
    assert outcomes and outcomes[0][0] is False
