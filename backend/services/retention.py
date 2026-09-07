"""Retention: reviews.db must not grow forever. Every review keeps quoted
lines of the code it reviewed, so a year is the default and 0 keeps all.

sweep() deletes reviews (with their findings) and webhook deliveries older
than REVIEW_RETENTION_DAYS, never a row that is still running or queued.
run_nightly() sweeps at startup and then once a day until cancelled. What
is worth keeping longer is exported first with scripts/export_reviews.py."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from config.logging import get_logger
from config.settings import Settings
from database.repositories.review_repository import ReviewRepository
from database.repositories.webhook_repository import WebhookRepository

logger = get_logger(__name__)
DAY_SECONDS = 24 * 60 * 60


def cutoff_for(settings: Settings, now: Optional[datetime] = None) -> Optional[datetime]:
    """The moment before which rows go, or None when everything is kept."""
    if settings.REVIEW_RETENTION_DAYS <= 0:
        return None
    return (now or datetime.now(timezone.utc)) - timedelta(days=settings.REVIEW_RETENTION_DAYS)


async def sweep(session_factory: async_sessionmaker, settings: Settings, now: Optional[datetime] = None) -> Dict[str, int]:
    cutoff = cutoff_for(settings, now)
    if cutoff is None:
        return {"reviews": 0, "findings": 0, "deliveries": 0}
    async with session_factory() as session:
        counts = await ReviewRepository(session).delete_older_than(cutoff)
        counts["deliveries"] = await WebhookRepository(session).delete_older_than(cutoff)
    if any(counts.values()):
        logger.info("retention sweep", days=settings.REVIEW_RETENTION_DAYS, **counts)
    return counts


async def run_nightly(session_factory: async_sessionmaker, settings: Settings, interval_seconds: float = DAY_SECONDS) -> None:
    """Sweep now and then every interval, until cancelled. A sweep that fails
    is logged and tried again next time; it never stops the loop."""
    while True:
        try:
            await sweep(session_factory, settings)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("retention sweep failed", error=type(e).__name__)
        await asyncio.sleep(interval_seconds)
