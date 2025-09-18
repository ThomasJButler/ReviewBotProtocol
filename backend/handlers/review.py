"""Review API handlers for manual code reviews and PR analysis."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uuid
import time

from config.logging import get_logger, review_logger
from config.settings import settings
from models.review import (
    ManualReviewRequest, FileReviewRequest, PRReviewRequest,
    ReviewResponse, ReviewResultResponse, ReviewListResponse, ReviewStatsResponse
)
from models.api import APIResponse, APIStatus, PaginationMeta
from models.github import PRAnalysisRequest
from services.ai_reviewer import AIReviewer
from services.github_client import GitHubClient
from services.queue_processor import add_review_to_queue, queue_processor
from database.connection import get_db_session
from database.repositories.review_repository import ReviewRepository
from utils.helpers import get_utc_timestamp

logger = get_logger(__name__)
review_router = APIRouter()


@review_router.post("/manual", response_model=ReviewResponse)
async def create_manual_review(
    request: ManualReviewRequest,
    background_tasks: BackgroundTasks,
    db_session = Depends(get_db_session)
):
    """
    Create a manual code review for provided code snippet.

    This endpoint accepts code content and performs AI-powered analysis
    including security, performance, and quality checks.
    """
    try:
        review_id = str(uuid.uuid4())

        logger.info(f"Starting manual review {review_id}")

        # Create review record
        repo = ReviewRepository(db_session)
        review_data = {
            "id": review_id,
            "type": "manual",
            "status": "pending",
            "configuration": request.configuration.dict() if request.configuration else {},
            "created_at": get_utc_timestamp()
        }

        review = await repo.create_review(review_data)

        # Process review in background
        background_tasks.add_task(
            process_manual_review,
            review_id,
            request.code,
            request.language,
            request.filename
        )

        return ReviewResponse(
            review_id=review_id,
            status="pending",
            message="Manual review queued for processing",
            created_at=review.created_at,
            estimated_completion=None
        )

    except Exception as e:
        logger.error(f"Failed to create manual review: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.post("/files", response_model=ReviewResponse)
async def create_file_review(
    request: FileReviewRequest,
    background_tasks: BackgroundTasks,
    db_session = Depends(get_db_session)
):
    """
    Create a review for multiple uploaded files.

    This endpoint accepts multiple files and performs comprehensive
    analysis across all provided files.
    """
    try:
        review_id = str(uuid.uuid4())

        logger.info(f"Starting file review {review_id} for {len(request.files)} files")

        # Create review record
        repo = ReviewRepository(db_session)
        review_data = {
            "id": review_id,
            "type": "manual",
            "status": "pending",
            "configuration": request.configuration.dict() if request.configuration else {},
            "created_at": get_utc_timestamp()
        }

        review = await repo.create_review(review_data)

        # Process review in background
        background_tasks.add_task(
            process_file_review,
            review_id,
            request.files
        )

        return ReviewResponse(
            review_id=review_id,
            status="pending",
            message=f"File review queued for {len(request.files)} files",
            created_at=review.created_at
        )

    except Exception as e:
        logger.error(f"Failed to create file review: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.post("/pr", response_model=ReviewResponse)
async def create_pr_review(
    request: PRReviewRequest,
    background_tasks: BackgroundTasks,
    db_session = Depends(get_db_session)
):
    """
    Create a review for a GitHub pull request.

    This endpoint triggers analysis of a specific PR and posts
    inline comments with findings.
    """
    try:
        review_id = str(uuid.uuid4())

        logger.info(
            f"Starting PR review {review_id}",
            repository=request.repository,
            pr_number=request.pr_number
        )

        # Create review record
        repo = ReviewRepository(db_session)
        review_data = {
            "id": review_id,
            "type": "pr_webhook",
            "status": "pending",
            "repository": request.repository,
            "pr_number": request.pr_number,
            "configuration": request.configuration.dict() if request.configuration else {},
            "created_at": get_utc_timestamp()
        }

        review = await repo.create_review(review_data)

        # Convert to analysis request
        analysis_request = PRAnalysisRequest(
            repository=request.repository,
            pr_number=request.pr_number,
            include_security=request.configuration.include_security if request.configuration else True,
            include_performance=request.configuration.include_performance if request.configuration else True,
            include_quality=request.configuration.include_quality if request.configuration else True,
            force_refresh=request.force_refresh
        )

        # Add to queue (requires GitHub App installation)
        # Note: This would need installation_id from GitHub App
        # For now, we'll process immediately
        background_tasks.add_task(
            process_pr_review,
            review_id,
            analysis_request
        )

        return ReviewResponse(
            review_id=review_id,
            status="pending",
            message=f"PR review queued for {request.repository}#{request.pr_number}",
            created_at=review.created_at
        )

    except Exception as e:
        logger.error(f"Failed to create PR review: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.get("/{review_id}", response_model=ReviewResultResponse)
async def get_review_result(
    review_id: str,
    db_session = Depends(get_db_session)
):
    """Get review results by ID."""
    try:
        repo = ReviewRepository(db_session)
        review = await repo.get_review_by_id(review_id)

        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        # Convert to response format
        review_dict = {
            "id": str(review.id),
            "type": review.type,
            "status": review.status,
            "repository": review.repository,
            "pr_number": review.pr_number,
            "overall_score": review.overall_score,
            "total_issues": review.total_issues,
            "created_at": review.created_at,
            "started_at": review.started_at,
            "completed_at": review.completed_at,
            "processing_time": review.processing_time,
            "issues": [
                {
                    "id": str(issue.id),
                    "category": issue.category,
                    "severity": issue.severity,
                    "title": issue.title,
                    "message": issue.message,
                    "file_path": issue.file_path,
                    "line_number": issue.line_number,
                    "code_snippet": issue.code_snippet,
                    "suggestion": issue.suggestion,
                    "rule_id": issue.rule_id
                }
                for issue in review.issues
            ]
        }

        # Generate summary
        if review.status == "completed":
            summary = f"Review completed with score {review.overall_score}/10. Found {review.total_issues} issues."
        elif review.status == "failed":
            summary = f"Review failed: {review.error_message}"
        else:
            summary = f"Review is {review.status}"

        recommendations = []
        if review.overall_score < 7:
            recommendations.append("Address critical and high severity issues before merging")
        if review.security_issues_count > 0:
            recommendations.append("Review security vulnerabilities carefully")
        if review.overall_score >= 8:
            recommendations.append("Code quality is good, ready for merge")

        return ReviewResultResponse(
            review=review_dict,
            summary=summary,
            recommendations=recommendations
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get review {review_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.get("/", response_model=ReviewListResponse)
async def list_reviews(
    repository: Optional[str] = Query(None, description="Filter by repository"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db_session = Depends(get_db_session)
):
    """List reviews with optional filtering."""
    try:
        repo = ReviewRepository(db_session)

        offset = (page - 1) * per_page

        if repository:
            reviews = await repo.get_reviews_by_repository(
                repository=repository,
                limit=per_page,
                offset=offset,
                status=status
            )
        else:
            reviews = await repo.search_reviews(
                query="",
                status=status,
                limit=per_page,
                offset=offset
            )

        # Convert to response format
        review_dicts = []
        for review in reviews:
            review_dicts.append({
                "id": str(review.id),
                "type": review.type,
                "status": review.status,
                "repository": review.repository,
                "pr_number": review.pr_number,
                "overall_score": review.overall_score,
                "total_issues": review.total_issues,
                "created_at": review.created_at,
                "completed_at": review.completed_at,
                "processing_time": review.processing_time
            })

        # Calculate pagination
        total_count = len(review_dicts)  # This is a simplified count
        has_next = len(reviews) == per_page
        has_prev = page > 1

        pagination = PaginationMeta(
            page=page,
            per_page=per_page,
            total=total_count,
            pages=(total_count + per_page - 1) // per_page,
            has_next=has_next,
            has_prev=has_prev
        )

        return ReviewListResponse(
            reviews=review_dicts,
            total=total_count,
            page=page,
            per_page=per_page,
            has_next=has_next,
            has_prev=has_prev
        )

    except Exception as e:
        logger.error(f"Failed to list reviews: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.get("/stats/overview", response_model=ReviewStatsResponse)
async def get_review_statistics(
    repository: Optional[str] = Query(None, description="Filter by repository"),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    db_session = Depends(get_db_session)
):
    """Get review statistics and metrics."""
    try:
        from datetime import timedelta

        repo = ReviewRepository(db_session)

        end_date = get_utc_timestamp()
        start_date = end_date - timedelta(days=days)

        # Get review statistics
        review_stats = await repo.get_review_statistics(
            repository=repository,
            start_date=start_date,
            end_date=end_date
        )

        # Get issue statistics
        issue_stats = await repo.get_issue_statistics(
            repository=repository,
            start_date=start_date,
            end_date=end_date
        )

        return ReviewStatsResponse(
            total_reviews=review_stats["total_reviews"],
            completed_reviews=review_stats["status_counts"].get("completed", 0),
            failed_reviews=review_stats["status_counts"].get("failed", 0),
            avg_processing_time=review_stats["average_processing_time"],
            avg_score=review_stats["average_score"],
            common_issues=[
                {"rule_id": rule_id, "count": count}
                for rule_id, count in issue_stats["common_rules"].items()
            ],
            reviews_by_repository={repository: review_stats["total_reviews"]} if repository else {},
            reviews_by_date={}  # Could be enhanced with daily breakdowns
        )

    except Exception as e:
        logger.error(f"Failed to get review statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    db_session = Depends(get_db_session)
):
    """Delete a review and its associated issues."""
    try:
        repo = ReviewRepository(db_session)
        success = await repo.delete_review(review_id)

        if not success:
            raise HTTPException(status_code=404, detail="Review not found")

        return {"message": f"Review {review_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete review {review_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.get("/queue/status")
async def get_queue_status():
    """Get current queue status and statistics."""
    try:
        stats = await queue_processor.get_queue_stats()
        return {
            "queue_stats": stats,
            "worker_status": "running" if queue_processor.is_running else "stopped",
            "timestamp": get_utc_timestamp()
        }

    except Exception as e:
        logger.error(f"Failed to get queue status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task functions

async def process_manual_review(
    review_id: str,
    code: str,
    language: Optional[str],
    filename: Optional[str]
):
    """Process a manual code review."""
    start_time = time.time()

    try:
        logger.info(f"Processing manual review {review_id}")

        # Initialize AI reviewer
        ai_reviewer = AIReviewer()

        # Create a mock file for processing
        from models.github import PRFile
        mock_file = PRFile(
            filename=filename or "code.txt",
            status="added",
            additions=len(code.split('\n')),
            deletions=0,
            changes=len(code.split('\n')),
            blob_url="",
            raw_url="",
            contents_url="",
            patch=f"+{code.replace(chr(10), chr(10) + '+')}"  # Convert to diff format
        )

        # Process the code
        results = await ai_reviewer.review_pr_files([mock_file])

        # Update review in database
        from database.connection import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            repo = ReviewRepository(session)

            # Update review status
            processing_time = time.time() - start_time
            update_data = {
                "status": "completed",
                "overall_score": results["overall_score"],
                "total_issues": results["total_issues"],
                "security_issues_count": len(results["security_issues"]),
                "performance_issues_count": len(results["performance_issues"]),
                "quality_issues_count": len(results["quality_issues"]),
                "processing_time": processing_time,
                "completed_at": get_utc_timestamp(),
                "ai_model_used": "gpt-4o",
                "ai_tokens_used": results["ai_metrics"]["total_tokens"],
                "ai_cost": results["ai_metrics"]["total_cost"]
            }

            await repo.update_review(review_id, update_data)

            # Add issues
            issues_data = []
            for file_result in results["files_reviewed"]:
                for issue_list, category in [
                    (file_result["security_issues"], "security"),
                    (file_result["performance_issues"], "performance"),
                    (file_result["quality_issues"], "quality")
                ]:
                    for issue in issue_list:
                        issues_data.append({
                            "category": category,
                            "severity": issue.get("severity", "medium"),
                            "title": issue.get("type", "Issue detected"),
                            "message": issue.get("description", ""),
                            "file_path": filename,
                            "line_number": issue.get("line_number"),
                            "code_snippet": issue.get("code_snippet"),
                            "suggestion": issue.get("recommendation"),
                            "rule_id": issue.get("type")
                        })

            if issues_data:
                await repo.add_issues_to_review(review_id, issues_data)

        review_logger.review_completed(
            filename or "manual",
            0,
            processing_time,
            results["overall_score"],
            0
        )

        logger.info(f"Manual review {review_id} completed successfully")

    except Exception as e:
        logger.error(f"Manual review {review_id} failed: {str(e)}")

        # Update review as failed
        try:
            from database.connection import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                repo = ReviewRepository(session)
                await repo.update_review(review_id, {
                    "status": "failed",
                    "error_message": str(e),
                    "completed_at": get_utc_timestamp()
                })
        except Exception as db_error:
            logger.error(f"Failed to update failed review {review_id}: {str(db_error)}")


async def process_file_review(review_id: str, files: List[Dict[str, str]]):
    """Process a multi-file review."""
    # Similar to process_manual_review but handles multiple files
    logger.info(f"Processing file review {review_id} for {len(files)} files")
    # Implementation would be similar to manual review but iterate over files


async def process_pr_review(review_id: str, analysis_request: PRAnalysisRequest):
    """Process a PR review."""
    logger.info(f"Processing PR review {review_id} for {analysis_request.repository}#{analysis_request.pr_number}")
    # Implementation would use GitHubClient to fetch PR data and process