"""Repository for managing review data access."""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
import uuid

from ..models import Review, ReviewIssue
from config.logging import get_logger

logger = get_logger(__name__)


class ReviewRepository:
    """Repository for review operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_review(self, review_data: Dict[str, Any]) -> Review:
        """Create a new review record."""
        try:
            review = Review(**review_data)
            self.session.add(review)
            await self.session.commit()
            await self.session.refresh(review)

            logger.info(f"Created review {review.id}", repository=review.repository)
            return review

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create review: {str(e)}")
            raise

    async def get_review_by_id(self, review_id: str) -> Optional[Review]:
        """Get review by ID with issues loaded."""
        try:
            stmt = select(Review).options(
                selectinload(Review.issues)
            ).where(Review.id == review_id)

            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get review {review_id}: {str(e)}")
            raise

    async def get_reviews_by_repository(
        self,
        repository: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Review]:
        """Get reviews for a repository."""
        try:
            stmt = select(Review).where(Review.repository == repository)

            if status:
                stmt = stmt.where(Review.status == status)

            stmt = stmt.order_by(desc(Review.created_at)).limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to get reviews for {repository}: {str(e)}")
            raise

    async def get_pr_review(self, repository: str, pr_number: int) -> Optional[Review]:
        """Get review for a specific PR."""
        try:
            stmt = select(Review).options(
                selectinload(Review.issues)
            ).where(
                and_(
                    Review.repository == repository,
                    Review.pr_number == pr_number
                )
            ).order_by(desc(Review.created_at))

            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get PR review {repository}#{pr_number}: {str(e)}")
            raise

    async def update_review(self, review_id: str, update_data: Dict[str, Any]) -> Optional[Review]:
        """Update an existing review."""
        try:
            review = await self.get_review_by_id(review_id)
            if not review:
                return None

            for key, value in update_data.items():
                if hasattr(review, key):
                    setattr(review, key, value)

            await self.session.commit()
            await self.session.refresh(review)

            logger.info(f"Updated review {review_id}")
            return review

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update review {review_id}: {str(e)}")
            raise

    async def delete_review(self, review_id: str) -> bool:
        """Delete a review and its issues."""
        try:
            review = await self.get_review_by_id(review_id)
            if not review:
                return False

            await self.session.delete(review)
            await self.session.commit()

            logger.info(f"Deleted review {review_id}")
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete review {review_id}: {str(e)}")
            raise

    async def add_issues_to_review(self, review_id: str, issues_data: List[Dict[str, Any]]) -> List[ReviewIssue]:
        """Add issues to a review."""
        try:
            issues = []
            for issue_data in issues_data:
                issue_data["review_id"] = review_id
                issue = ReviewIssue(**issue_data)
                self.session.add(issue)
                issues.append(issue)

            await self.session.commit()

            # Refresh to get generated IDs
            for issue in issues:
                await self.session.refresh(issue)

            logger.info(f"Added {len(issues)} issues to review {review_id}")
            return issues

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to add issues to review {review_id}: {str(e)}")
            raise

    async def get_review_statistics(
        self,
        repository: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get review statistics."""
        try:
            # Base query
            base_query = select(Review)

            if repository:
                base_query = base_query.where(Review.repository == repository)

            if start_date:
                base_query = base_query.where(Review.created_at >= start_date)

            if end_date:
                base_query = base_query.where(Review.created_at <= end_date)

            # Total reviews
            total_stmt = select(func.count()).select_from(base_query.subquery())
            total_result = await self.session.execute(total_stmt)
            total_reviews = total_result.scalar()

            # Reviews by status
            status_stmt = select(
                Review.status,
                func.count(Review.id)
            ).select_from(base_query.subquery()).group_by(Review.status)

            status_result = await self.session.execute(status_stmt)
            status_counts = dict(status_result.all())

            # Average scores and processing times
            avg_stmt = select(
                func.avg(Review.overall_score),
                func.avg(Review.processing_time),
                func.avg(Review.total_issues)
            ).select_from(base_query.where(Review.status == "completed").subquery())

            avg_result = await self.session.execute(avg_stmt)
            avg_score, avg_time, avg_issues = avg_result.first()

            return {
                "total_reviews": total_reviews,
                "status_counts": status_counts,
                "average_score": float(avg_score) if avg_score else 0.0,
                "average_processing_time": float(avg_time) if avg_time else 0.0,
                "average_issues": float(avg_issues) if avg_issues else 0.0,
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            }

        except Exception as e:
            logger.error(f"Failed to get review statistics: {str(e)}")
            raise

    async def get_issue_statistics(
        self,
        repository: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get issue statistics."""
        try:
            # Base query joining reviews and issues
            base_query = select(ReviewIssue).join(Review)

            if repository:
                base_query = base_query.where(Review.repository == repository)

            if start_date:
                base_query = base_query.where(Review.created_at >= start_date)

            if end_date:
                base_query = base_query.where(Review.created_at <= end_date)

            # Issues by category
            category_stmt = select(
                ReviewIssue.category,
                func.count(ReviewIssue.id)
            ).select_from(base_query.subquery()).group_by(ReviewIssue.category)

            category_result = await self.session.execute(category_stmt)
            category_counts = dict(category_result.all())

            # Issues by severity
            severity_stmt = select(
                ReviewIssue.severity,
                func.count(ReviewIssue.id)
            ).select_from(base_query.subquery()).group_by(ReviewIssue.severity)

            severity_result = await self.session.execute(severity_stmt)
            severity_counts = dict(severity_result.all())

            # Most common rules
            rule_stmt = select(
                ReviewIssue.rule_id,
                func.count(ReviewIssue.id)
            ).select_from(
                base_query.where(ReviewIssue.rule_id.isnot(None)).subquery()
            ).group_by(ReviewIssue.rule_id).order_by(desc(func.count(ReviewIssue.id))).limit(10)

            rule_result = await self.session.execute(rule_stmt)
            common_rules = dict(rule_result.all())

            return {
                "category_counts": category_counts,
                "severity_counts": severity_counts,
                "common_rules": common_rules
            }

        except Exception as e:
            logger.error(f"Failed to get issue statistics: {str(e)}")
            raise

    async def get_recent_reviews(self, limit: int = 10) -> List[Review]:
        """Get recent reviews across all repositories."""
        try:
            stmt = select(Review).order_by(desc(Review.created_at)).limit(limit)
            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to get recent reviews: {str(e)}")
            raise

    async def search_reviews(
        self,
        query: str,
        repository: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Review]:
        """Search reviews by text query."""
        try:
            stmt = select(Review)

            # Add text search conditions
            search_conditions = []
            if query:
                search_term = f"%{query}%"
                search_conditions.extend([
                    Review.repository.ilike(search_term),
                    Review.error_message.ilike(search_term)
                ])

            if search_conditions:
                stmt = stmt.where(or_(*search_conditions))

            # Add filters
            if repository:
                stmt = stmt.where(Review.repository == repository)

            if status:
                stmt = stmt.where(Review.status == status)

            stmt = stmt.order_by(desc(Review.created_at)).limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to search reviews: {str(e)}")
            raise

    async def cleanup_old_reviews(self, days_old: int = 30) -> int:
        """Clean up old completed reviews."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            # Get reviews to delete
            stmt = select(Review).where(
                and_(
                    Review.status == "completed",
                    Review.created_at < cutoff_date
                )
            )

            result = await self.session.execute(stmt)
            reviews_to_delete = result.scalars().all()

            # Delete reviews (issues will be cascade deleted)
            for review in reviews_to_delete:
                await self.session.delete(review)

            await self.session.commit()

            logger.info(f"Cleaned up {len(reviews_to_delete)} old reviews")
            return len(reviews_to_delete)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to cleanup old reviews: {str(e)}")
            raise