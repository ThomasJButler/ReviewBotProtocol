"""Background task processing and queue management for code reviews."""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum

try:
    import redis.asyncio as redis
except ImportError:
    import redis

from config.settings import settings
from config.logging import get_logger, review_logger, github_logger
from models.github import WebhookDelivery, PRAnalysisRequest
from models.review import CodeReview, ReviewStatus, ReviewType
from services.github_client import GitHubClient
from services.ai_reviewer import AIReviewer
from utils.helpers import get_utc_timestamp, retry_async

logger = get_logger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ReviewTask:
    """Review task model."""

    def __init__(
        self,
        task_id: str,
        task_type: str,
        priority: TaskPriority,
        payload: Dict[str, Any],
        created_at: Optional[datetime] = None
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.priority = priority
        self.payload = payload
        self.created_at = created_at or get_utc_timestamp()
        self.status = TaskStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.retry_count = 0
        self.max_retries = 3
        self.error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_message": self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReviewTask':
        """Create task from dictionary."""
        task = cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            priority=TaskPriority(data["priority"]),
            payload=data["payload"],
            created_at=datetime.fromisoformat(data["created_at"])
        )
        task.status = TaskStatus(data["status"])
        task.started_at = datetime.fromisoformat(data["started_at"]) if data["started_at"] else None
        task.completed_at = datetime.fromisoformat(data["completed_at"]) if data["completed_at"] else None
        task.retry_count = data["retry_count"]
        task.max_retries = data["max_retries"]
        task.error_message = data["error_message"]
        return task


class QueueProcessor:
    """Background queue processor for review tasks."""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.is_running = False
        self.worker_tasks: List[asyncio.Task] = []
        self.max_concurrent_reviews = 3
        self.processing_semaphore = asyncio.Semaphore(self.max_concurrent_reviews)

        # Queue names
        self.urgent_queue = "review_queue:urgent"
        self.high_queue = "review_queue:high"
        self.normal_queue = "review_queue:normal"
        self.low_queue = "review_queue:low"
        self.processing_key = "review_queue:processing"
        self.completed_key = "review_queue:completed"
        self.failed_key = "review_queue:failed"

    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                retry_on_timeout=True,
                socket_connect_timeout=5
            )

            # Test connection
            await self.redis_client.ping()
            logger.info("Connected to Redis for queue processing")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            # Fallback to in-memory processing if Redis is not available
            self.redis_client = None

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")

    async def add_task(self, task: ReviewTask) -> bool:
        """Add a task to the appropriate queue."""
        try:
            if not self.redis_client:
                # Fallback: process immediately if no Redis
                await self._process_task_immediate(task)
                return True

            # Determine queue based on priority
            queue_name = self._get_queue_name(task.priority)

            # Serialize task
            task_data = json.dumps(task.to_dict())

            # Add to queue
            await self.redis_client.lpush(queue_name, task_data)

            logger.info(
                f"Added task {task.task_id} to {queue_name}",
                task_type=task.task_type,
                priority=task.priority
            )

            return True

        except Exception as e:
            logger.error(f"Failed to add task to queue: {str(e)}")
            # Fallback: try to process immediately
            try:
                await self._process_task_immediate(task)
                return True
            except Exception as fallback_error:
                logger.error(f"Fallback processing also failed: {str(fallback_error)}")
                return False

    async def start_workers(self, num_workers: int = 2):
        """Start background worker tasks."""
        if self.is_running:
            logger.warning("Workers already running")
            return

        self.is_running = True
        logger.info(f"Starting {num_workers} queue workers")

        # Start worker tasks
        for i in range(num_workers):
            worker_task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self.worker_tasks.append(worker_task)

        # Start cleanup task
        cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.worker_tasks.append(cleanup_task)

    async def stop_workers(self):
        """Stop all worker tasks."""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("Stopping queue workers")

        # Cancel all worker tasks
        for task in self.worker_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        self.worker_tasks.clear()
        logger.info("All queue workers stopped")

    async def _worker_loop(self, worker_id: str):
        """Main worker loop to process tasks."""
        logger.info(f"Worker {worker_id} started")

        while self.is_running:
            try:
                # Get next task from queues (priority order)
                task = await self._get_next_task()

                if task:
                    async with self.processing_semaphore:
                        await self._process_task(task, worker_id)
                else:
                    # No tasks available, wait a bit
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying

        logger.info(f"Worker {worker_id} stopped")

    async def _get_next_task(self) -> Optional[ReviewTask]:
        """Get the next task from queues (priority order)."""
        if not self.redis_client:
            return None

        # Check queues in priority order
        queues = [
            self.urgent_queue,
            self.high_queue,
            self.normal_queue,
            self.low_queue
        ]

        for queue_name in queues:
            try:
                # Non-blocking pop from queue
                task_data = await self.redis_client.rpop(queue_name)
                if task_data:
                    task_dict = json.loads(task_data)
                    task = ReviewTask.from_dict(task_dict)

                    # Move to processing set
                    await self.redis_client.sadd(self.processing_key, task.task_id)

                    return task

            except Exception as e:
                logger.error(f"Error getting task from {queue_name}: {str(e)}")

        return None

    async def _process_task(self, task: ReviewTask, worker_id: str):
        """Process a single review task."""
        start_time = time.time()
        task.started_at = get_utc_timestamp()
        task.status = TaskStatus.PROCESSING

        logger.info(
            f"Worker {worker_id} processing task {task.task_id}",
            task_type=task.task_type,
            priority=task.priority
        )

        try:
            if task.task_type == "pr_review":
                await self._process_pr_review_task(task)
            elif task.task_type == "manual_review":
                await self._process_manual_review_task(task)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")

            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = get_utc_timestamp()

            processing_time = time.time() - start_time

            logger.info(
                f"Task {task.task_id} completed successfully",
                worker_id=worker_id,
                processing_time=processing_time
            )

        except Exception as e:
            processing_time = time.time() - start_time
            task.error_message = str(e)

            logger.error(
                f"Task {task.task_id} failed",
                worker_id=worker_id,
                error=str(e),
                processing_time=processing_time
            )

            # Handle retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.RETRYING

                # Add back to queue with exponential backoff
                delay = 2 ** task.retry_count
                await asyncio.sleep(delay)

                logger.info(f"Retrying task {task.task_id} (attempt {task.retry_count})")
                await self.add_task(task)
            else:
                task.status = TaskStatus.FAILED
                logger.error(f"Task {task.task_id} failed permanently after {task.max_retries} retries")

        finally:
            # Remove from processing set
            if self.redis_client:
                await self.redis_client.srem(self.processing_key, task.task_id)

                # Add to completed or failed set
                if task.status == TaskStatus.COMPLETED:
                    await self.redis_client.sadd(self.completed_key, json.dumps(task.to_dict()))
                elif task.status == TaskStatus.FAILED:
                    await self.redis_client.sadd(self.failed_key, json.dumps(task.to_dict()))

    async def _process_pr_review_task(self, task: ReviewTask):
        """Process a PR review task."""
        payload = task.payload
        repo_full_name = payload["repository"]
        pr_number = payload["pr_number"]
        installation_id = payload["installation_id"]

        review_logger.review_started(repo_full_name, pr_number, 0)

        # Initialize clients
        github_client = GitHubClient(installation_id)
        ai_reviewer = AIReviewer()

        # Get PR information
        pr_info = await github_client.get_pr_info(repo_full_name, pr_number)
        head_sha = pr_info["head"]["sha"]

        # Get PR files
        pr_files = await github_client.get_pr_files(repo_full_name, pr_number)

        if not pr_files:
            logger.warning(f"No files found for PR #{pr_number}")
            return

        # Run AI review
        review_results = await ai_reviewer.review_pr_files(pr_files)

        # Post review comments
        comments_posted = 0
        for file_result in review_results["files_reviewed"]:
            filename = file_result["filename"]

            # Post security issues as comments
            for issue in file_result["security_issues"]:
                if issue.get("line_number"):
                    try:
                        comment_body = format_review_comment(
                            "security",
                            issue.get("severity", "medium"),
                            issue.get("description", "Security issue detected"),
                            issue.get("recommendation"),
                            issue.get("line_number")
                        )

                        await github_client.post_review_comment(
                            repo_full_name,
                            pr_number,
                            comment_body,
                            head_sha,
                            filename,
                            issue["line_number"]
                        )
                        comments_posted += 1

                    except Exception as e:
                        logger.error(f"Failed to post comment: {str(e)}")

            # Post performance issues (limit to avoid spam)
            for issue in file_result["performance_issues"][:3]:  # Max 3 per file
                if issue.get("line_number") and issue.get("severity") in ["high", "medium"]:
                    try:
                        comment_body = format_review_comment(
                            "performance",
                            issue.get("severity", "medium"),
                            issue.get("description", "Performance issue detected"),
                            issue.get("recommendation"),
                            issue.get("line_number")
                        )

                        await github_client.post_review_comment(
                            repo_full_name,
                            pr_number,
                            comment_body,
                            head_sha,
                            filename,
                            issue["line_number"]
                        )
                        comments_posted += 1

                    except Exception as e:
                        logger.error(f"Failed to post performance comment: {str(e)}")

        # Update status check
        status_state = "success" if review_results["overall_score"] >= 7.0 else "failure"
        status_description = f"AI Review: {review_results['overall_score']:.1f}/10 - {review_results['total_issues']} issues found"

        await github_client.create_status_check(
            repo_full_name,
            head_sha,
            status_state,
            status_description,
            "git-review-assistant/review"
        )

        review_logger.review_completed(
            repo_full_name,
            pr_number,
            review_results["processing_time"],
            review_results["overall_score"],
            comments_posted
        )

        logger.info(
            f"PR review completed",
            repository=repo_full_name,
            pr_number=pr_number,
            score=review_results["overall_score"],
            issues=review_results["total_issues"],
            comments_posted=comments_posted
        )

    async def _process_manual_review_task(self, task: ReviewTask):
        """Process a manual review task."""
        # Implementation for manual code review
        logger.info(f"Processing manual review task {task.task_id}")
        # TODO: Implement manual review processing

    async def _process_task_immediate(self, task: ReviewTask):
        """Process task immediately (fallback when Redis unavailable)."""
        logger.warning(f"Processing task {task.task_id} immediately (no queue)")
        await self._process_task(task, "immediate")

    async def _cleanup_loop(self):
        """Cleanup old completed and failed tasks."""
        while self.is_running:
            try:
                await self._cleanup_old_tasks()
                await asyncio.sleep(3600)  # Run every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _cleanup_old_tasks(self):
        """Remove old completed and failed tasks."""
        if not self.redis_client:
            return

        cutoff_time = get_utc_timestamp() - timedelta(days=7)  # Keep for 7 days

        for key in [self.completed_key, self.failed_key]:
            try:
                # Get all tasks
                tasks = await self.redis_client.smembers(key)

                for task_data in tasks:
                    try:
                        task_dict = json.loads(task_data)
                        completed_at = datetime.fromisoformat(task_dict.get("completed_at", ""))

                        if completed_at < cutoff_time:
                            await self.redis_client.srem(key, task_data)

                    except (json.JSONDecodeError, ValueError, TypeError):
                        # Remove invalid task data
                        await self.redis_client.srem(key, task_data)

            except Exception as e:
                logger.error(f"Error cleaning up {key}: {str(e)}")

    def _get_queue_name(self, priority: TaskPriority) -> str:
        """Get queue name for priority level."""
        return {
            TaskPriority.URGENT: self.urgent_queue,
            TaskPriority.HIGH: self.high_queue,
            TaskPriority.NORMAL: self.normal_queue,
            TaskPriority.LOW: self.low_queue
        }[priority]

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self.redis_client:
            return {"error": "Redis not available"}

        try:
            stats = {}

            # Queue lengths
            for priority in TaskPriority:
                queue_name = self._get_queue_name(priority)
                length = await self.redis_client.llen(queue_name)
                stats[f"{priority}_queue"] = length

            # Processing count
            stats["processing"] = await self.redis_client.scard(self.processing_key)

            # Completed/failed counts
            stats["completed"] = await self.redis_client.scard(self.completed_key)
            stats["failed"] = await self.redis_client.scard(self.failed_key)

            return stats

        except Exception as e:
            logger.error(f"Error getting queue stats: {str(e)}")
            return {"error": str(e)}


# Global queue processor instance
queue_processor = QueueProcessor()


# Helper functions for adding tasks to queue

async def add_review_to_queue(
    review_request: PRAnalysisRequest,
    installation_id: int,
    webhook_delivery: WebhookDelivery,
    priority: str = "normal"
) -> Dict[str, Any]:
    """Add a PR review to the processing queue."""
    try:
        task_id = str(uuid.uuid4())

        task = ReviewTask(
            task_id=task_id,
            task_type="pr_review",
            priority=TaskPriority(priority),
            payload={
                "repository": review_request.repository,
                "pr_number": review_request.pr_number,
                "installation_id": installation_id,
                "webhook_delivery_id": webhook_delivery.id,
                "include_security": review_request.include_security,
                "include_performance": review_request.include_performance,
                "include_quality": review_request.include_quality,
                "force_refresh": review_request.force_refresh
            }
        )

        success = await queue_processor.add_task(task)

        return {
            "success": success,
            "task_id": task_id,
            "message": f"Review queued for {review_request.repository}#{review_request.pr_number}"
        }

    except Exception as e:
        logger.error(f"Failed to queue review: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def format_review_comment(comment_type: str, severity: str, message: str,
                         suggestion: str = None, line_number: int = None) -> str:
    """Format a review comment with proper markdown and emoji."""
    # Import here to avoid circular imports
    from utils.helpers import format_review_comment as format_comment
    return format_comment(comment_type, severity, message, suggestion, line_number)