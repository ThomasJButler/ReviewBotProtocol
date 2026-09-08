"""The real wiring: app lifespan starts the real queue with the real runner.
A signed webhook comes back 202 straight away, and the review then runs to a
completed row using the fake GitHub API and the fake model."""

import json

import httpx
import respx

from tests.conftest import TEST_LOCAL_TOKEN, webhook_headers
from tests.fakes import RecordingChatModel
from tests.test_runner import MODEL_REPLY, _routes

AUTH = {"Authorization": f"Bearer {TEST_LOCAL_TOKEN}"}


@respx.mock
def test_webhook_to_completed_review_through_the_real_queue(app, fresh_db_url, pr_payload):
    from fastapi.testclient import TestClient
    from services.review_queue import ReviewQueue
    reviews_route = _routes(head="a" * 40)
    with TestClient(app, base_url="http://localhost") as c:
        queue = app.state.queue
        assert isinstance(queue, ReviewQueue) and queue.alive
        assert not app.state.retention.done(), "the nightly retention sweep runs beside the queue"
        app.state.deps.llm = RecordingChatModel(response=MODEL_REPLY)
        body = json.dumps(pr_payload).encode()
        r = c.post("/webhook/github", content=body, headers=webhook_headers(body, delivery="live-1"))
        assert r.status_code == 202 and r.json()["outcome"] == "queued"
        c.portal.call(lambda: queue.drain(timeout=30))
        listing = c.get("/api/reviews", headers=AUTH).json()
    assert app.state.retention.done(), "and is cancelled at shutdown, before the engine goes"
    assert reviews_route.called
    assert listing["total"] == 1 and listing["items"][0]["status"] == "completed" and listing["items"][0]["findings_count"] == 1
    assert listing["items"][0]["head_sha"] == "a" * 40


def test_rows_left_running_are_marked_interrupted_at_startup(app, fresh_db_url):
    import asyncio
    from fastapi.testclient import TestClient
    from database.connection import close_db, init_db
    from database.repositories.review_repository import ReviewRepository
    from database.repositories.webhook_repository import WebhookRepository

    async def seed():
        factory = await init_db(fresh_db_url)
        async with factory() as s:
            await ReviewRepository(s).create({"repository": "o/r", "pr_number": 1, "status": "running"})
            await WebhookRepository(s).record("d-run", "pull_request", "opened", "o/r", 1, "a" * 40)
            await WebhookRepository(s).mark("d-run", "running")
        await close_db()
    asyncio.run(seed())
    with TestClient(app, base_url="http://localhost") as c:
        items = c.get("/api/reviews", headers=AUTH).json()["items"]
        deliveries = c.get("/api/deliveries", headers=AUTH).json()["items"]
    assert items[0]["status"] == "interrupted" and deliveries[0]["status"] == "interrupted"
