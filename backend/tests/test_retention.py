"""reviews.db must not grow forever: the nightly sweep and the export."""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.settings import settings
from database.models import WebhookDelivery
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
        await w.record("d-old", "pull_request", "opened", "o/r", 1, "a" * 40)
        await w.record("d-new", "pull_request", "opened", "o/r", 3, "b" * 40)
        (await s.get(WebhookDelivery, "d-old")).received_at = OLD
        await s.commit()


async def test_the_sweep_deletes_old_reviews_with_their_findings_and_keeps_the_rest(db):
    await _seed(db)
    counts = await sweep(db, settings.model_copy(update={"REVIEW_RETENTION_DAYS": 365}), now=NOW)
    assert counts == {"reviews": 1, "findings": 2, "deliveries": 1}
    async with db() as s:
        repo = ReviewRepository(s)
        assert await repo.get("old") is None
        assert (await repo.get("old-running")).status == "running", "a row still running is never swept"
        assert len((await repo.get("new")).findings) == 1
        assert [d.delivery_id for d in await WebhookRepository(s).recent(5)] == ["d-new"]


async def test_zero_days_keeps_everything(db):
    await _seed(db)
    forever = settings.model_copy(update={"REVIEW_RETENTION_DAYS": 0})
    assert cutoff_for(forever, NOW) is None
    assert await sweep(db, forever, now=NOW) == {"reviews": 0, "findings": 0, "deliveries": 0}
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
