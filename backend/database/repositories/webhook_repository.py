"""Webhook deliveries: the replay check and the status trail."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import WebhookDelivery


class WebhookRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(self, delivery_id: str, event: str, action: Optional[str], repository: Optional[str],
                     pr_number: Optional[int], head_sha: Optional[str], body_sha256: Optional[str] = None) -> bool:
        """Insert the delivery. Returns False if this delivery id, or this exact
        signed body under any delivery id, was seen before, unless the earlier
        attempt failed or was interrupted, in which case GitHub's redelivery is
        accepted and the row reused. The delivery id is idempotency for GitHub's
        own redelivery; the body hash is what the signature actually covers, so
        a captured body replayed under a fresh id is still a replay. The read
        then the insert is a race on paper; the unique index on the hash
        makes the loser's insert an IntegrityError, answered as a replay."""
        existing = await self.session.get(WebhookDelivery, delivery_id)
        if existing is None and body_sha256:
            stmt = select(WebhookDelivery).where(WebhookDelivery.body_sha256 == body_sha256).limit(1)
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            if existing.status not in ("failed", "interrupted"):
                return False
            existing.status = "received"
            existing.review_id = None
            await self.session.commit()
            return True
        self.session.add(WebhookDelivery(delivery_id=delivery_id, event=event, action=action, repository=repository,
                                         pr_number=pr_number, head_sha=head_sha, body_sha256=body_sha256, status="received"))
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            return False
        return True

    async def mark(self, delivery_id: Optional[str], status: str, review_id: Optional[str] = None,
                   commit: bool = True) -> None:
        if not delivery_id:
            return
        row = await self.session.get(WebhookDelivery, delivery_id)
        if row is None:
            return
        row.status = status
        if review_id:
            row.review_id = review_id
        if commit:
            await self.session.commit()

    async def mark_interrupted(self) -> int:
        result = await self.session.execute(
            update(WebhookDelivery).where(WebhookDelivery.status.in_(("queued", "running"))).values(status="interrupted"))
        await self.session.commit()
        return int(result.rowcount or 0)

    async def expire_older_than(self, cutoff: datetime) -> int:
        """Deliveries received before the cutoff are stripped to a tombstone, not
        deleted: the delivery id, the SHA-256 of the signed body, the event and
        the received time stay, with status "expired"; the repository, pull
        request, head, action and review link go. GitHub's HMAC carries no
        timestamp, so the stored hash is the only thing that makes a captured
        body a replay, and it has to outlive the review data. record() reads any
        status outside failed and interrupted as a duplicate, so a tombstone
        refuses a replay with no other code; a failed or interrupted row past
        the cutoff expires too, since a body that old arriving again is a
        replay rather than a redelivery. Queued and running rows are left alone,
        and an expired row is not rewritten, so each row is counted once."""
        result = await self.session.execute(
            update(WebhookDelivery)
            .where(WebhookDelivery.received_at < cutoff, WebhookDelivery.status.notin_(("queued", "running", "expired")))
            .values(status="expired", action=None, repository=None, pr_number=None, head_sha=None, review_id=None))
        await self.session.commit()
        return int(result.rowcount or 0)

    async def recent(self, limit: int = 20) -> List[WebhookDelivery]:
        stmt = select(WebhookDelivery).order_by(desc(WebhookDelivery.received_at)).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())
