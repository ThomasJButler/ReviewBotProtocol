"""GitHub webhook handlers for the Git Review Assistant."""

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
import json
import time
from typing import Dict, Any

from config.logging import get_logger, security_logger, review_logger
from config.settings import settings
from utils.crypto import verify_github_signature
from utils.helpers import extract_pr_info, get_utc_timestamp
from models.github import (
    PRWebhookPayload, GitHubEventType, PRAction,
    WebhookDelivery, PRAnalysisRequest
)
from models.api import WebhookResponse, APIStatus
from services.queue_processor import add_review_to_queue
from services.github_client import GitHubClient

logger = get_logger(__name__)
webhook_router = APIRouter()


async def verify_webhook_signature(request: Request) -> tuple[bytes, str]:
    """
    Verify GitHub webhook signature and return payload and event type.

    Returns:
        tuple: (payload_bytes, event_type)

    Raises:
        HTTPException: If signature verification fails
    """
    # Get signature from headers
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        security_logger.logger.warning("Webhook received without signature")
        raise HTTPException(
            status_code=400,
            detail="Missing X-Hub-Signature-256 header"
        )

    # Get event type
    event_type = request.headers.get("X-GitHub-Event")
    if not event_type:
        raise HTTPException(
            status_code=400,
            detail="Missing X-GitHub-Event header"
        )

    # Get payload
    payload = await request.body()
    if not payload:
        raise HTTPException(
            status_code=400,
            detail="Empty payload"
        )

    # Verify signature
    #if not verify_github_signature(payload, signature):
        #security_logger.logger.error(
        #    "Webhook signature verification failed",
        #    event_type=event_type,
         #   payload_size=len(payload)
        #)
        #raise HTTPException(
         #   status_code=401,
          #  detail="Invalid webhook signature"
        #)

    #return payload, event_type


@webhook_router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks
) -> WebhookResponse:
    """
    Handle GitHub webhook events.

    This endpoint receives and processes GitHub webhook events,
    particularly pull request events for automated code review.
    """
    start_time = time.time()

    try:
        # Verify webhook signature and get payload
        payload_bytes, event_type = await verify_webhook_signature(request)

        # Parse JSON payload
        try:
            payload = json.loads(payload_bytes.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse webhook payload: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON payload"
            )

        # Get delivery ID for tracking
        delivery_id = request.headers.get("X-GitHub-Delivery", "unknown")

        # Log webhook reception
        repo_name = payload.get("repository", {}).get("full_name", "unknown")
        sender = payload.get("sender", {}).get("login", "unknown")

        security_logger.webhook_received(event_type, repo_name, sender)

        logger.info(
            "Webhook received",
            event_type=event_type,
            delivery_id=delivery_id,
            repository=repo_name,
            sender=sender,
            payload_size=len(payload_bytes)
        )

        # Store webhook delivery record
        webhook_delivery = WebhookDelivery(
            id=f"{delivery_id}_{int(time.time())}",
            event_type=GitHubEventType(event_type),
            delivery_id=delivery_id,
            received_at=get_utc_timestamp(),
            repository=repo_name
        )

        # Process based on event type
        processing_result = None

        if event_type == GitHubEventType.PULL_REQUEST:
            processing_result = await handle_pull_request_event(
                payload, background_tasks, webhook_delivery
            )
        elif event_type == GitHubEventType.PULL_REQUEST_REVIEW:
            processing_result = await handle_pr_review_event(
                payload, background_tasks, webhook_delivery
            )
        elif event_type == GitHubEventType.PULL_REQUEST_REVIEW_COMMENT:
            processing_result = await handle_pr_review_comment_event(
                payload, background_tasks, webhook_delivery
            )
        elif event_type == GitHubEventType.PUSH:
            processing_result = await handle_push_event(
                payload, background_tasks, webhook_delivery
            )
        else:
            logger.info(f"Unhandled event type: {event_type}")
            processing_result = {
                "message": f"Event type {event_type} acknowledged but not processed",
                "actions_taken": []
            }

        processing_time = time.time() - start_time

        logger.info(
            "Webhook processed successfully",
            event_type=event_type,
            delivery_id=delivery_id,
            processing_time=processing_time,
            actions=processing_result.get("actions_taken", [])
        )

        return WebhookResponse(
            status=APIStatus.SUCCESS,
            message=processing_result["message"],
            event_type=event_type,
            event_id=delivery_id,
            processing_time=processing_time,
            actions_taken=processing_result.get("actions_taken", [])
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(
            "Webhook processing failed",
            error=str(e),
            error_type=type(e).__name__,
            processing_time=processing_time
        )

        return WebhookResponse(
            status=APIStatus.ERROR,
            message=f"Webhook processing failed: {str(e)}",
            event_type=event_type if 'event_type' in locals() else "unknown",
            event_id=delivery_id if 'delivery_id' in locals() else "unknown",
            processing_time=processing_time
        )


async def handle_pull_request_event(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    webhook_delivery: WebhookDelivery
) -> Dict[str, Any]:
    """Handle pull request webhook events."""

    try:
        # Parse payload
        pr_payload = PRWebhookPayload(**payload)
        action = pr_payload.action
        pr = pr_payload.pull_request
        repo = pr_payload.repository

        webhook_delivery.pr_number = pr.number

        logger.info(
            "Processing PR event",
            action=action,
            pr_number=pr.number,
            repository=repo.full_name,
            author=pr.user.login
        )

        actions_taken = []

        # Handle different PR actions
        if action in [PRAction.OPENED, PRAction.SYNCHRONIZE, PRAction.REOPENED]:
            # Trigger automated review for new/updated PRs

            # Skip draft PRs unless configured otherwise
            if pr.draft and not settings.DEBUG:
                logger.info(f"Skipping review for draft PR #{pr.number}")
                return {
                    "message": f"Draft PR #{pr.number} acknowledged, review skipped",
                    "actions_taken": ["skipped_draft_pr"]
                }

            # Create review request
            review_request = PRAnalysisRequest(
                repository=repo.full_name,
                pr_number=pr.number,
                include_security=True,
                include_performance=True,
                include_quality=True
            )

            # Add to background processing queue
            queue_result = await add_review_to_queue(
                review_request=review_request,
                installation_id=pr_payload.installation.id,
                webhook_delivery=webhook_delivery,
                priority="normal" if action == PRAction.OPENED else "high"
            )

            if queue_result["success"]:
                actions_taken.append("queued_for_review")
                review_logger.review_started(
                    repo.full_name,
                    pr.number,
                    pr.changed_files or 0
                )

                # Post initial status check
                await post_initial_status_check(
                    repo.full_name,
                    pr.head.sha,
                    pr_payload.installation.id
                )
                actions_taken.append("posted_status_check")

            message = f"PR #{pr.number} {action} - review queued for processing"

        elif action == PRAction.CLOSED:
            # Clean up any pending reviews
            message = f"PR #{pr.number} closed - cleaning up pending reviews"
            actions_taken.append("cleanup_reviews")

        elif action == PRAction.READY_FOR_REVIEW:
            # Handle draft -> ready transition
            review_request = PRAnalysisRequest(
                repository=repo.full_name,
                pr_number=pr.number
            )

            queue_result = await add_review_to_queue(
                review_request=review_request,
                installation_id=pr_payload.installation.id,
                webhook_delivery=webhook_delivery,
                priority="high"
            )

            if queue_result["success"]:
                actions_taken.append("queued_for_review")

            message = f"PR #{pr.number} marked ready for review - analysis queued"

        else:
            message = f"PR #{pr.number} {action} - no action required"

        return {
            "message": message,
            "actions_taken": actions_taken
        }

    except Exception as e:
        logger.error(f"Failed to handle PR event: {str(e)}")
        raise


async def handle_pr_review_event(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    webhook_delivery: WebhookDelivery
) -> Dict[str, Any]:
    """Handle pull request review events."""

    review = payload.get("review", {})
    pr = payload.get("pull_request", {})
    action = payload.get("action")

    logger.info(
        "Processing PR review event",
        action=action,
        pr_number=pr.get("number"),
        review_state=review.get("state"),
        reviewer=review.get("user", {}).get("login")
    )

    # For now, just acknowledge the event
    # Could implement review aggregation, conflict detection, etc.

    return {
        "message": f"PR review {action} acknowledged",
        "actions_taken": ["acknowledged_review"]
    }


async def handle_pr_review_comment_event(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    webhook_delivery: WebhookDelivery
) -> Dict[str, Any]:
    """Handle pull request review comment events."""

    comment = payload.get("comment", {})
    pr = payload.get("pull_request", {})
    action = payload.get("action")

    logger.info(
        "Processing PR review comment event",
        action=action,
        pr_number=pr.get("number"),
        commenter=comment.get("user", {}).get("login")
    )

    # Could implement comment analysis, bot interaction, etc.

    return {
        "message": f"PR review comment {action} acknowledged",
        "actions_taken": ["acknowledged_comment"]
    }


async def handle_push_event(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    webhook_delivery: WebhookDelivery
) -> Dict[str, Any]:
    """Handle push events (optional functionality)."""

    ref = payload.get("ref", "")
    repo = payload.get("repository", {})
    commits = payload.get("commits", [])

    logger.info(
        "Processing push event",
        ref=ref,
        repository=repo.get("full_name"),
        commits_count=len(commits)
    )

    # For now, just acknowledge
    # Could implement branch protection, pre-commit hooks, etc.

    return {
        "message": f"Push to {ref} acknowledged",
        "actions_taken": ["acknowledged_push"]
    }


async def post_initial_status_check(
    repo_full_name: str,
    commit_sha: str,
    installation_id: int
) -> bool:
    """Post initial 'pending' status check to GitHub."""

    try:
        github_client = GitHubClient(installation_id)

        await github_client.create_status_check(
            repo_full_name,
            commit_sha,
            state="pending",
            description="AI code review in progress...",
            context="git-review-assistant/review"
        )

        logger.info(
            "Posted initial status check",
            repository=repo_full_name,
            commit_sha=commit_sha[:8]
        )
        return True

    except Exception as e:
        logger.error(
            "Failed to post initial status check",
            repository=repo_full_name,
            commit_sha=commit_sha[:8],
            error=str(e)
        )
        return False


@webhook_router.get("/github/health")
async def webhook_health():
    """Health check endpoint for webhook service."""
    return {
        "status": "healthy",
        "webhook_endpoint": "/webhook/github",
        "supported_events": [
            "pull_request",
            "pull_request_review",
            "pull_request_review_comment",
            "push"
        ],
        "timestamp": get_utc_timestamp()
    }


@webhook_router.post("/github/test")
async def test_webhook():
    """Test endpoint for webhook validation (development only)."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    return {
        "message": "Webhook test endpoint",
        "timestamp": get_utc_timestamp(),
        "config": {
            "webhook_secret_configured": bool(settings.GITHUB_WEBHOOK_SECRET),
            "app_id_configured": bool(settings.GITHUB_APP_ID)
        }
    }