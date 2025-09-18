"""Repository for managing webhook delivery data."""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from datetime import datetime, timedelta

from ..models import WebhookDelivery
from config.logging import get_logger

logger = get_logger(__name__)


class WebhookRepository:
    """Repository for webhook delivery operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_webhook_delivery(self, webhook_data: Dict[str, Any]) -> WebhookDelivery:
        """Create a new webhook delivery record."""
        try:
            webhook = WebhookDelivery(**webhook_data)
            self.session.add(webhook)
            await self.session.commit()
            await self.session.refresh(webhook)

            logger.info(f"Created webhook delivery {webhook.id}")
            return webhook

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create webhook delivery: {str(e)}")
            raise

    async def get_webhook_delivery_by_id(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """Get webhook delivery by ID."""
        try:
            stmt = select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get webhook delivery {delivery_id}: {str(e)}")
            raise

    async def update_webhook_delivery(
        self,
        delivery_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[WebhookDelivery]:
        """Update webhook delivery status and results."""
        try:
            webhook = await self.get_webhook_delivery_by_id(delivery_id)
            if not webhook:
                return None

            for key, value in update_data.items():
                if hasattr(webhook, key):
                    setattr(webhook, key, value)

            await self.session.commit()
            await self.session.refresh(webhook)

            logger.info(f"Updated webhook delivery {delivery_id}")
            return webhook

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update webhook delivery {delivery_id}: {str(e)}")
            raise

    async def get_webhook_deliveries_by_repository(
        self,
        repository: str,
        limit: int = 50,
        offset: int = 0,
        event_type: Optional[str] = None
    ) -> List[WebhookDelivery]:
        """Get webhook deliveries for a repository."""
        try:
            stmt = select(WebhookDelivery).where(WebhookDelivery.repository == repository)

            if event_type:
                stmt = stmt.where(WebhookDelivery.event_type == event_type)

            stmt = stmt.order_by(desc(WebhookDelivery.received_at)).limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to get webhook deliveries for {repository}: {str(e)}")
            raise

    async def get_pending_webhook_deliveries(self, limit: int = 100) -> List[WebhookDelivery]:
        """Get pending webhook deliveries."""
        try:
            stmt = select(WebhookDelivery).where(
                WebhookDelivery.status == "pending"
            ).order_by(WebhookDelivery.received_at).limit(limit)

            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to get pending webhook deliveries: {str(e)}")
            raise

    async def get_failed_webhook_deliveries(
        self,
        limit: int = 50,
        since: Optional[datetime] = None
    ) -> List[WebhookDelivery]:
        """Get failed webhook deliveries."""
        try:
            stmt = select(WebhookDelivery).where(WebhookDelivery.status == "failed")

            if since:
                stmt = stmt.where(WebhookDelivery.received_at >= since)

            stmt = stmt.order_by(desc(WebhookDelivery.received_at)).limit(limit)

            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to get failed webhook deliveries: {str(e)}")
            raise

    async def get_webhook_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get webhook delivery statistics."""
        try:
            base_query = select(WebhookDelivery)

            if start_date:
                base_query = base_query.where(WebhookDelivery.received_at >= start_date)

            if end_date:
                base_query = base_query.where(WebhookDelivery.received_at <= end_date)

            # Total deliveries
            total_stmt = select(func.count()).select_from(base_query.subquery())
            total_result = await self.session.execute(total_stmt)
            total_deliveries = total_result.scalar()

            # Deliveries by status
            status_stmt = select(
                WebhookDelivery.status,
                func.count(WebhookDelivery.id)
            ).select_from(base_query.subquery()).group_by(WebhookDelivery.status)

            status_result = await self.session.execute(status_stmt)
            status_counts = dict(status_result.all())

            # Deliveries by event type
            event_stmt = select(
                WebhookDelivery.event_type,
                func.count(WebhookDelivery.id)
            ).select_from(base_query.subquery()).group_by(WebhookDelivery.event_type)

            event_result = await self.session.execute(event_stmt)
            event_counts = dict(event_result.all())

            # Average processing time
            avg_stmt = select(
                func.avg(WebhookDelivery.processing_time)
            ).select_from(
                base_query.where(WebhookDelivery.processing_time.isnot(None)).subquery()
            )

            avg_result = await self.session.execute(avg_stmt)
            avg_processing_time = avg_result.scalar()

            return {
                "total_deliveries": total_deliveries,
                "status_counts": status_counts,
                "event_counts": event_counts,
                "average_processing_time": float(avg_processing_time) if avg_processing_time else 0.0,
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            }

        except Exception as e:
            logger.error(f"Failed to get webhook statistics: {str(e)}")
            raise

    async def cleanup_old_webhook_deliveries(self, days_old: int = 30) -> int:
        """Clean up old webhook delivery records."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            # Get deliveries to delete
            stmt = select(WebhookDelivery).where(
                and_(
                    WebhookDelivery.status.in_(["completed", "failed"]),
                    WebhookDelivery.received_at < cutoff_date
                )
            )

            result = await self.session.execute(stmt)
            deliveries_to_delete = result.scalars().all()

            # Delete deliveries
            for delivery in deliveries_to_delete:
                await self.session.delete(delivery)

            await self.session.commit()

            logger.info(f"Cleaned up {len(deliveries_to_delete)} old webhook deliveries")
            return len(deliveries_to_delete)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to cleanup old webhook deliveries: {str(e)}")
            raise

    async def get_repository_webhook_health(self, repository: str) -> Dict[str, Any]:
        """Get webhook health metrics for a repository."""
        try:
            # Recent deliveries (last 24 hours)
            since = datetime.utcnow() - timedelta(hours=24)

            recent_stmt = select(
                WebhookDelivery.status,
                func.count(WebhookDelivery.id)
            ).where(
                and_(
                    WebhookDelivery.repository == repository,
                    WebhookDelivery.received_at >= since
                )
            ).group_by(WebhookDelivery.status)

            recent_result = await self.session.execute(recent_stmt)
            recent_counts = dict(recent_result.all())

            # Last successful delivery
            last_success_stmt = select(WebhookDelivery.received_at).where(
                and_(
                    WebhookDelivery.repository == repository,
                    WebhookDelivery.status == "completed"
                )
            ).order_by(desc(WebhookDelivery.received_at)).limit(1)

            last_success_result = await self.session.execute(last_success_stmt)
            last_success = last_success_result.scalar_one_or_none()

            # Average processing time (last 100 deliveries)
            avg_time_stmt = select(
                func.avg(WebhookDelivery.processing_time)
            ).where(
                and_(
                    WebhookDelivery.repository == repository,
                    WebhookDelivery.processing_time.isnot(None)
                )
            ).order_by(desc(WebhookDelivery.received_at)).limit(100)

            avg_time_result = await self.session.execute(avg_time_stmt)
            avg_processing_time = avg_time_result.scalar()

            # Calculate health score (0-100)
            total_recent = sum(recent_counts.values())
            success_rate = (recent_counts.get("completed", 0) / total_recent * 100) if total_recent > 0 else 100

            health_score = success_rate
            if avg_processing_time and avg_processing_time > 30:  # Slow processing
                health_score *= 0.8
            if not last_success or last_success < datetime.utcnow() - timedelta(hours=6):
                health_score *= 0.5

            return {
                "repository": repository,
                "health_score": min(100, max(0, health_score)),
                "recent_deliveries": recent_counts,
                "last_successful_delivery": last_success.isoformat() if last_success else None,
                "average_processing_time": float(avg_processing_time) if avg_processing_time else 0.0,
                "status": "healthy" if health_score >= 80 else "degraded" if health_score >= 50 else "unhealthy"
            }

        except Exception as e:
            logger.error(f"Failed to get webhook health for {repository}: {str(e)}")
            raise