"""Reviews and findings."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Finding, Review


class ReviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: Dict[str, Any]) -> Review:
        review = Review(**data)
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def update(self, review_id: str, data: Dict[str, Any], commit: bool = True) -> Optional[Review]:
        review = await self.session.get(Review, review_id)
        if review is None:
            return None
        for key, value in data.items():
            if hasattr(review, key):
                setattr(review, key, value)
        if commit:
            await self.session.commit()
        return review

    async def add_findings(self, review_id: str, findings: List[Dict[str, Any]], commit: bool = True) -> int:
        for f in findings:
            self.session.add(Finding(review_id=review_id, **f))
        if commit:
            await self.session.commit()
        return len(findings)

    async def completed_for(self, repository: str, pr_number: int, head_sha: str) -> Optional[Review]:
        """A completed review of exactly this head, if one exists."""
        stmt = select(Review).where(Review.repository == repository, Review.pr_number == pr_number,
                                    Review.head_sha == head_sha, Review.status == "completed").limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def running_for(self, repository: str, pr_number: int, head_sha: str) -> Optional[Review]:
        """The review of this head that is running now, for the status page's progress line."""
        stmt = select(Review).where(Review.repository == repository, Review.pr_number == pr_number,
                                    Review.head_sha == head_sha, Review.status == "running").limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get(self, review_id: str) -> Optional[Review]:
        stmt = select(Review).options(selectinload(Review.findings)).where(Review.id == review_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self, repository: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Review]:
        stmt = select(Review)
        if repository:
            stmt = stmt.where(Review.repository == repository)
        stmt = stmt.order_by(desc(Review.created_at)).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def count(self, repository: Optional[str] = None) -> int:
        stmt = select(func.count(Review.id))
        if repository:
            stmt = stmt.where(Review.repository == repository)
        return int((await self.session.execute(stmt)).scalar() or 0)

    async def set_useful(self, review_id: str, useful: Optional[bool]) -> bool:
        review = await self.session.get(Review, review_id)
        if review is None:
            return False
        review.useful = useful
        await self.session.commit()
        return True

    async def mark_interrupted(self) -> int:
        """Rows left 'running' by a process that died. Called at startup."""
        result = await self.session.execute(
            update(Review).where(Review.status == "running").values(status="interrupted", error_message="the backend stopped while this review was running"))
        await self.session.commit()
        return int(result.rowcount or 0)

    async def delete_older_than(self, cutoff: datetime) -> Dict[str, int]:
        """Reviews created before the cutoff, with their findings, unless still
        running or queued. Keyed on created_at, which every row has; completed_at
        is null on a row the process never finished, and such a row must not
        live forever. The findings go first and explicitly: the ORM cascade does
        not reach a bulk delete and SQLite's foreign keys are not enforced."""
        old = select(Review.id).where(Review.created_at < cutoff, Review.status.notin_(("running", "queued")))
        findings = await self.session.execute(delete(Finding).where(Finding.review_id.in_(old)))
        reviews = await self.session.execute(delete(Review).where(Review.id.in_(old)))
        await self.session.commit()
        return {"reviews": int(reviews.rowcount or 0), "findings": int(findings.rowcount or 0)}

    async def repositories(self) -> List[str]:
        stmt = select(Review.repository).distinct().order_by(Review.repository)
        return [r for (r,) in (await self.session.execute(stmt)).all()]
