"""reviews.db must not grow forever: the nightly sweep and the export."""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.settings import settings
from database.models import WebhookDelivery
from tests.conftest import TEST_LOCAL_TOKEN, webhook_headers
from database.repositories.review_repository import ReviewRepository
from database.repositories.webhook_repository import WebhookRepository
from services.retention import cutoff_for, run_nightly, sweep

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_reviews  # noqa: E402

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=400)
FINDING = {"path": "a.py", "line": 2, "category": "security", "severity": "high", "title": "t", "evidence": "e",
           "recommendation": "r", "confidence": 0.9}


async def _seed(db):
    async with db() as s:
        repo = ReviewRepository(s)
        await repo.create({"id": "old", "repository": "o/r", "pr_number": 1, "status": "completed", "created_at": OLD})
        await repo.add_findings("old", [FINDING, FINDING])
        await repo.create({"id": "old-running", "repository": "o/r", "pr_number": 2, "status": "running", "created_at": OLD})
        await repo.create({"id": "new", "repository": "o/r", "pr_number": 3, "status": "completed", "created_at": NOW - timedelta(days=1)})
        await repo.add_findings("new", [FINDING])
        w = WebhookRepository(s)
        # a real hash on every row: the replay check only fires on a truthy hash, so a NULL one pins nothing
        await w.record("d-old", "pull_request", "opened", "o/r", 1, "a" * 40, body_sha256="1" * 64)
        await w.record("d-new", "pull_request", "opened", "o/r", 3, "b" * 40, body_sha256="2" * 64)
        (await s.get(WebhookDelivery, "d-old")).received_at = OLD
        await s.commit()


async def test_the_sweep_deletes_old_reviews_and_expires_old_deliveries_to_a_tombstone(db):
    await _seed(db)
    counts = await sweep(db, settings.model_copy(update={"REVIEW_RETENTION_DAYS": 365}), now=NOW)
    assert counts == {"reviews": 1, "findings": 2, "deliveries_expired": 1}
    async with db() as s:
        repo = ReviewRepository(s)
        assert await repo.get("old") is None
        assert (await repo.get("old-running")).status == "running", "a row still running is never swept"
        assert len((await repo.get("new")).findings) == 1
        assert [d.delivery_id for d in await WebhookRepository(s).recent(5)] == ["d-new", "d-old"], "the tombstone stays"
        old = await s.get(WebhookDelivery, "d-old")
        assert old.status == "expired" and old.body_sha256 == "1" * 64 and old.event == "pull_request" and old.received_at is not None
        assert (old.action, old.repository, old.pr_number, old.head_sha, old.review_id) == (None, None, None, None, None)
        new = await s.get(WebhookDelivery, "d-new")
        assert (new.status, new.repository, new.pr_number, new.head_sha) == ("received", "o/r", 3, "b" * 40), "a recent row is untouched"


async def test_a_second_sweep_expires_nothing_and_a_queued_delivery_is_never_expired_however_old_it_is(db):
    await _seed(db)
    async with db() as s:
        w = WebhookRepository(s)
        await w.record("d-stuck", "pull_request", "opened", "o/r", 4, "c" * 40, body_sha256="3" * 64)
        await w.mark("d-stuck", "queued")
        (await s.get(WebhookDelivery, "d-stuck")).received_at = OLD
        await s.commit()
    year = settings.model_copy(update={"REVIEW_RETENTION_DAYS": 365})
    assert (await sweep(db, year, now=NOW))["deliveries_expired"] == 1
    assert (await sweep(db, year, now=NOW))["deliveries_expired"] == 0, "an expired row is not rewritten and counted again"
    async with db() as s:
        stuck = await s.get(WebhookDelivery, "d-stuck")
        # mark_interrupted at startup gives such a row a terminal status, so a crashed row expires at the next boot
        assert stuck.status == "queued" and stuck.repository == "o/r" and stuck.pr_number == 4


def _post(client, body, delivery):
    return client.post("/webhook/github", content=body, headers=webhook_headers(body, delivery=delivery))


async def test_a_captured_body_replayed_after_the_retention_sweep_is_still_a_duplicate(db, client, stub_queue, pr_payload):
    """The 2026-09-08 scan's F1, end to end: the sweep used to delete the delivery
    row, and with it the only record that makes a year-old signed body a replay."""
    body = json.dumps(pr_payload).encode()
    assert _post(client, body, "d-1").status_code == 202 and len(stub_queue.submissions) == 1
    async with db() as s:
        row = await s.get(WebhookDelivery, "d-1")
        row.status, row.received_at = "completed", OLD  # the stub queue leaves it queued; make it a finished, year-old delivery
        await s.commit()
    assert (await sweep(db, settings.model_copy(update={"REVIEW_RETENTION_DAYS": 365}), now=NOW))["deliveries_expired"] == 1
    replay = _post(client, body, "d-2")
    assert replay.status_code == 200 and replay.json()["status"] == "duplicate"
    assert len(stub_queue.submissions) == 1, "no review row ever existed, so the tombstone's hash is the only thing refusing it"


async def test_a_failed_delivery_is_redeliverable_until_the_sweep_makes_it_a_tombstone(db):
    async with db() as s:
        w = WebhookRepository(s)
        await w.record("d-f", "pull_request", "opened", "o/r", 5, "d" * 40, body_sha256="4" * 64)
        await w.mark("d-f", "failed")
        assert await w.record("d-f2", "pull_request", "opened", "o/r", 5, "d" * 40, body_sha256="4" * 64) is True, "GitHub's redelivery of a failed delivery is accepted"
        row = await s.get(WebhookDelivery, "d-f")
        row.status, row.received_at = "failed", OLD
        await s.commit()
    assert (await sweep(db, settings.model_copy(update={"REVIEW_RETENTION_DAYS": 365}), now=NOW))["deliveries_expired"] == 1
    async with db() as s:
        assert await WebhookRepository(s).record("d-f3", "pull_request", "opened", "o/r", 5, "d" * 40, body_sha256="4" * 64) is False, \
            "a body older than the cutoff arriving again is a replay, not a redelivery"


async def test_the_deliveries_endpoint_serves_a_tombstone_with_nulls_where_the_metadata_was(db, client):
    await _seed(db)
    await sweep(db, settings.model_copy(update={"REVIEW_RETENTION_DAYS": 365}), now=NOW)
    rows = client.get("/api/deliveries", headers={"Authorization": f"Bearer {TEST_LOCAL_TOKEN}"}).json()["items"]
    old = next(r for r in rows if r["delivery_id"] == "d-old")
    assert set(old) == {"delivery_id", "event", "action", "repository", "pr_number", "head_sha", "status", "review_id", "received_at"}
    assert old["status"] == "expired" and old["event"] == "pull_request" and old["received_at"]
    assert (old["action"], old["repository"], old["pr_number"], old["head_sha"], old["review_id"]) == (None, None, None, None, None)


async def test_zero_days_keeps_everything(db):
    await _seed(db)
    forever = settings.model_copy(update={"REVIEW_RETENTION_DAYS": 0})
    assert cutoff_for(forever, NOW) is None
    assert await sweep(db, forever, now=NOW) == {"reviews": 0, "findings": 0, "deliveries_expired": 0}
    async with db() as s:
        assert await ReviewRepository(s).count() == 3


async def test_the_nightly_loop_sweeps_at_once_and_stops_when_cancelled(db, monkeypatch):
    await _seed(db)
    monkeypatch.setattr(settings, "REVIEW_RETENTION_DAYS", 365)
    task = asyncio.create_task(run_nightly(db, settings, interval_seconds=60))
    for _ in range(200):  # wait for the sweep, rather than sleeping a guessed amount and hoping
        await asyncio.sleep(0.02)
        async with db() as s:
            if await ReviewRepository(s).count() == 2:
                break
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert task.cancelled() or task.done()
    async with db() as s:
        assert await ReviewRepository(s).count() == 2, "the first sweep ran without waiting a day"


async def test_export_writes_every_selected_review_with_its_findings(db, fresh_db_url, tmp_path):
    await _seed(db)
    from database.connection import close_db
    await close_db()  # the script opens its own engine on the same file
    out = tmp_path / "reviews.json"
    assert await export_reviews.export(fresh_db_url, out, older_than_days=365, now=NOW) == 2
    data = json.loads(out.read_text())
    assert {r["id"] for r in data["reviews"]} == {"old", "old-running"}
    old = next(r for r in data["reviews"] if r["id"] == "old")
    assert len(old["findings"]) == 2 and old["findings"][0]["title"] == "t" and old["created_at"].startswith("2025-")
    assert await export_reviews.export(fresh_db_url, tmp_path / "all.json", repository="o/r") == 3
    later = await export_reviews.export(fresh_db_url, tmp_path / "later.json", older_than_days=365, now=NOW + timedelta(days=400))
    assert later == 3, "the cutoff moves with the clock it is given, so this test means the same thing next year"
