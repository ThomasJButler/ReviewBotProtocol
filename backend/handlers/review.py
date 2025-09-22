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
from services.metrics_service import MetricsService
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


@review_router.get("/history")
async def get_review_history(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    repository: Optional[str] = Query(None, description="Filter by repository"),
    status: Optional[str] = Query(None, description="Filter by status"),
    min_score: Optional[float] = Query(None, ge=0, le=10, description="Minimum score filter"),
    max_score: Optional[float] = Query(None, ge=0, le=10, description="Maximum score filter"),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="Sort order (asc/desc)"),
    db_session = Depends(get_db_session)
):
    """Get review history with advanced filtering and pagination."""
    try:
        from datetime import timedelta

        repo = ReviewRepository(db_session)

        # Build filters
        filters = {}
        if user_id:
            filters["created_by"] = user_id
        if repository:
            filters["repository"] = repository
        if status:
            filters["status"] = status

        # Date range filter
        end_date = get_utc_timestamp()
        start_date = end_date - timedelta(days=days)

        # Get reviews with filters
        reviews = await repo.get_filtered_reviews(
            filters=filters,
            min_score=min_score,
            max_score=max_score,
            start_date=start_date,
            end_date=end_date,
            limit=per_page,
            offset=(page - 1) * per_page,
            sort_by=sort_by,
            order=order
        )

        # Get total count for pagination
        total_count = await repo.count_filtered_reviews(
            filters=filters,
            min_score=min_score,
            max_score=max_score,
            start_date=start_date,
            end_date=end_date
        )

        # Format reviews for response
        review_history = []
        for review in reviews:
            review_history.append({
                "id": str(review.id),
                "type": review.type,
                "status": review.status,
                "repository": review.repository,
                "pr_number": review.pr_number,
                "overall_score": review.overall_score,
                "letter_grade": review.metrics.get("letter_grade") if review.metrics else None,
                "total_issues": review.total_issues,
                "security_issues": review.security_issues_count,
                "performance_issues": review.performance_issues_count,
                "quality_issues": review.quality_issues_count,
                "created_at": review.created_at,
                "processing_time": review.processing_time,
                "ai_model_used": review.ai_model_used,
                "code_suggestions": review.metrics.get("code_suggestions", []) if review.metrics else [],
                "priority_fixes": review.metrics.get("priority_fixes", []) if review.metrics else [],
            })

        return {
            "reviews": review_history,
            "pagination": {
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "pages": (total_count + per_page - 1) // per_page,
                "has_next": (page * per_page) < total_count,
                "has_prev": page > 1
            },
            "filters_applied": {
                "user_id": user_id,
                "repository": repository,
                "status": status,
                "min_score": min_score,
                "max_score": max_score,
                "days": days
            }
        }

    except Exception as e:
        logger.error(f"Failed to get review history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.get("/stats/user")
async def get_user_statistics(
    user_id: str = Query(..., description="User ID"),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    db_session = Depends(get_db_session)
):
    """Get user-specific review statistics and trends."""
    try:
        from datetime import timedelta

        repo = ReviewRepository(db_session)

        end_date = get_utc_timestamp()
        start_date = end_date - timedelta(days=days)

        # Get user's reviews
        user_reviews = await repo.get_filtered_reviews(
            filters={"created_by": user_id},
            start_date=start_date,
            end_date=end_date,
            limit=1000  # Get all reviews for statistics
        )

        if not user_reviews:
            return {
                "user_id": user_id,
                "total_reviews": 0,
                "average_score": 0,
                "total_issues_found": 0,
                "improvement_trend": 0,
                "top_issues": [],
                "repositories_reviewed": [],
                "review_frequency": "No reviews yet"
            }

        # Calculate statistics
        total_reviews = len(user_reviews)
        total_score = sum(r.overall_score for r in user_reviews)
        total_issues = sum(r.total_issues for r in user_reviews)

        # Calculate average score
        average_score = total_score / total_reviews if total_reviews > 0 else 0

        # Calculate improvement trend (compare first half to second half)
        if total_reviews > 1:
            mid_point = total_reviews // 2
            first_half_avg = sum(r.overall_score for r in user_reviews[:mid_point]) / mid_point
            second_half_avg = sum(r.overall_score for r in user_reviews[mid_point:]) / (total_reviews - mid_point)
            improvement_trend = second_half_avg - first_half_avg
        else:
            improvement_trend = 0

        # Get unique repositories
        repositories = list(set(r.repository for r in user_reviews if r.repository))

        # Count issue categories
        issue_counts = {
            "security": sum(r.security_issues_count for r in user_reviews),
            "performance": sum(r.performance_issues_count for r in user_reviews),
            "quality": sum(r.quality_issues_count for r in user_reviews)
        }

        # Calculate review frequency
        if total_reviews > 0:
            days_active = (user_reviews[-1].created_at - user_reviews[0].created_at).days + 1
            review_frequency = f"{total_reviews / max(days_active, 1):.1f} reviews/day"
        else:
            review_frequency = "No reviews"

        return {
            "user_id": user_id,
            "total_reviews": total_reviews,
            "average_score": round(average_score, 2),
            "total_issues_found": total_issues,
            "improvement_trend": round(improvement_trend, 2),
            "top_issues": [
                {"category": k, "count": v}
                for k, v in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
            ],
            "repositories_reviewed": repositories,
            "review_frequency": review_frequency,
            "best_review": max(user_reviews, key=lambda r: r.overall_score).overall_score if user_reviews else 0,
            "worst_review": min(user_reviews, key=lambda r: r.overall_score).overall_score if user_reviews else 0,
            "recent_activity": {
                "last_7_days": sum(1 for r in user_reviews if (end_date - r.created_at).days <= 7),
                "last_30_days": sum(1 for r in user_reviews if (end_date - r.created_at).days <= 30)
            }
        }

    except Exception as e:
        logger.error(f"Failed to get user statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.get("/compare/{review_id1}/{review_id2}")
async def compare_reviews(
    review_id1: str,
    review_id2: str,
    db_session = Depends(get_db_session)
):
    """Compare two reviews to show improvements or differences."""
    try:
        repo = ReviewRepository(db_session)

        # Get both reviews
        review1 = await repo.get_review_by_id(review_id1)
        review2 = await repo.get_review_by_id(review_id2)

        if not review1 or not review2:
            raise HTTPException(status_code=404, detail="One or both reviews not found")

        # Determine which is newer
        if review1.created_at > review2.created_at:
            newer, older = review1, review2
        else:
            newer, older = review2, review1

        # Calculate improvements
        score_diff = newer.overall_score - older.overall_score
        issues_diff = newer.total_issues - older.total_issues
        security_diff = newer.security_issues_count - older.security_issues_count

        # Compare issue categories
        newer_issues_by_category = {}
        older_issues_by_category = {}

        for issue in newer.issues:
            newer_issues_by_category[issue.category] = newer_issues_by_category.get(issue.category, 0) + 1

        for issue in older.issues:
            older_issues_by_category[issue.category] = older_issues_by_category.get(issue.category, 0) + 1

        # Find resolved and new issues
        resolved_issues = []
        new_issues = []

        # Simple comparison based on title and category
        older_issue_signatures = {(i.category, i.title) for i in older.issues}
        newer_issue_signatures = {(i.category, i.title) for i in newer.issues}

        for issue in older.issues:
            if (issue.category, issue.title) not in newer_issue_signatures:
                resolved_issues.append({
                    "category": issue.category,
                    "title": issue.title,
                    "severity": issue.severity
                })

        for issue in newer.issues:
            if (issue.category, issue.title) not in older_issue_signatures:
                new_issues.append({
                    "category": issue.category,
                    "title": issue.title,
                    "severity": issue.severity
                })

        return {
            "comparison": {
                "review1_id": str(review1.id),
                "review2_id": str(review2.id),
                "newer_review_id": str(newer.id),
                "older_review_id": str(older.id),
                "time_difference": str(newer.created_at - older.created_at)
            },
            "score_comparison": {
                "older_score": older.overall_score,
                "newer_score": newer.overall_score,
                "improvement": score_diff,
                "percentage_change": (score_diff / older.overall_score * 100) if older.overall_score > 0 else 0
            },
            "issues_comparison": {
                "older_total": older.total_issues,
                "newer_total": newer.total_issues,
                "issues_resolved": len(resolved_issues),
                "new_issues_found": len(new_issues),
                "net_change": issues_diff
            },
            "category_breakdown": {
                "older": older_issues_by_category,
                "newer": newer_issues_by_category
            },
            "resolved_issues": resolved_issues[:10],  # Top 10
            "new_issues": new_issues[:10],  # Top 10
            "improvement_summary": {
                "improved": score_diff > 0,
                "score_improved": score_diff > 0,
                "issues_reduced": issues_diff < 0,
                "security_improved": security_diff < 0
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare reviews: {str(e)}")
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


@review_router.post("/code")
async def review_code_direct(
    request: Dict[str, Any],
    db_session = Depends(get_db_session)
):
    """
    Direct code review endpoint for real-time analysis with database persistence.

    This endpoint provides immediate code review results and saves them to database.
    Used by the frontend for instant feedback on code snippets.
    """
    try:
        logger.info("Starting direct code review")

        # Extract files from request
        files_data = request.get("files", [])
        if not files_data:
            raise HTTPException(status_code=400, detail="No files provided")

        # Extract optional metadata
        user_id = request.get("user_id")
        repository = request.get("repository")

        # Create review record
        review_id = str(uuid.uuid4())
        repo = ReviewRepository(db_session)

        review_data = {
            "id": review_id,
            "type": "direct",
            "status": "in_progress",
            "repository": repository,
            "configuration": {
                "files_count": len(files_data),
                "source": "web_ui"
            },
            "created_by": user_id,
            "started_at": get_utc_timestamp()
        }

        review_record = await repo.create_review(review_data)

        # Initialize AI reviewer
        ai_reviewer = AIReviewer()

        # Convert to PRFile objects for processing
        from models.github import PRFile
        pr_files = []

        for file_data in files_data:
            # Create mock diff format if not provided
            content = file_data.get("content", file_data.get("patch", ""))

            # If it's raw content, convert to diff format
            if not content.startswith('+') and not content.startswith('-'):
                content = '+' + content.replace('\n', '\n+')

            pr_file = PRFile(
                filename=file_data.get("filename", "code.txt"),
                status=file_data.get("status", "modified"),
                additions=file_data.get("additions", len(content.split('\n'))),
                deletions=file_data.get("deletions", 0),
                changes=file_data.get("changes", len(content.split('\n'))),
                blob_url=file_data.get("blob_url", ""),
                raw_url=file_data.get("raw_url", ""),
                contents_url=file_data.get("contents_url", ""),
                patch=content
            )
            pr_files.append(pr_file)

        # Process the files with enhanced AI analysis
        start_time = time.time()
        results = await ai_reviewer.review_pr_files(pr_files)
        processing_time = time.time() - start_time

        # Update review record with results
        update_data = {
            "status": "completed",
            "overall_score": results.get("overall_score", 0),
            "total_issues": results.get("total_issues", 0),
            "security_issues_count": len(results.get("security_issues", [])),
            "performance_issues_count": len(results.get("performance_issues", [])),
            "quality_issues_count": len(results.get("quality_issues", [])),
            "processing_time": processing_time,
            "completed_at": get_utc_timestamp(),
            "ai_model_used": settings.OPENAI_MODEL,
            "ai_tokens_used": results.get("ai_metrics", {}).get("total_tokens", 0),
            "ai_cost": results.get("ai_metrics", {}).get("total_cost", 0),
            "metrics": {
                "letter_grade": results.get("letter_grade", "B"),
                "scoring_breakdown": results.get("scoring_breakdown", {}),
                "code_suggestions": results.get("code_suggestions", []),
                "priority_fixes": results.get("priority_fixes", []),
                "quick_wins": results.get("quick_wins", [])
            }
        }

        await repo.update_review(review_id, update_data)

        # Add issues to review
        issues_data = []
        for file_result in results.get("files_reviewed", []):
            filename = file_result.get("filename", "unknown")

            # Process all issue types
            issue_categories = [
                ("security_issues", "security"),
                ("performance_issues", "performance"),
                ("quality_issues", "quality"),
                ("documentation_issues", "documentation"),
                ("testing_issues", "testing"),
                ("architecture_issues", "architecture")
            ]

            for issue_list_key, category in issue_categories:
                for issue in file_result.get(issue_list_key, []):
                    issues_data.append({
                        "category": category,
                        "severity": issue.get("severity", "medium"),
                        "title": issue.get("type", "Issue detected"),
                        "message": issue.get("description", ""),
                        "file_path": filename,
                        "line_number": issue.get("line_number"),
                        "code_snippet": issue.get("code_snippet"),
                        "suggestion": issue.get("recommendation"),
                        "rule_id": issue.get("rule_id"),
                        "confidence_score": issue.get("confidence", 0.8)
                    })

        if issues_data:
            await repo.add_issues_to_review(review_id, issues_data)

        # Add review ID and processing time to results
        results["review_id"] = review_id
        results["analysis_time"] = f"{processing_time:.1f}s"
        results["saved_to_database"] = True

        logger.info(f"Direct code review {review_id} completed and saved in {processing_time:.2f}s")

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Direct code review failed: {str(e)}")

        # Try to update review as failed
        if 'review_id' in locals():
            try:
                await repo.update_review(review_id, {
                    "status": "failed",
                    "error_message": str(e),
                    "completed_at": get_utc_timestamp()
                })
            except:
                pass

        raise HTTPException(status_code=500, detail=f"Review failed: {str(e)}")


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


@review_router.get("/metrics/user/{user_id}")
async def get_user_metrics(
    user_id: str,
    days: int = Query(default=30, ge=1, le=365),
    db_session = Depends(get_db_session)
):
    """Get comprehensive metrics for a user's review activity."""
    try:
        metrics_service = MetricsService(db_session)
        metrics = await metrics_service.get_user_metrics(user_id, days)
        return metrics

    except Exception as e:
        logger.error(f"Failed to get user metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.get("/metrics/repository")
async def get_repository_metrics(
    repository: str = Query(..., description="Repository name"),
    days: int = Query(default=30, ge=1, le=365),
    db_session = Depends(get_db_session)
):
    """Get metrics for a specific repository."""
    try:
        metrics_service = MetricsService(db_session)
        metrics = await metrics_service.get_repository_metrics(repository, days)
        return metrics

    except Exception as e:
        logger.error(f"Failed to get repository metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.get("/metrics/trending")
async def get_trending_issues(
    days: int = Query(default=7, ge=1, le=30),
    limit: int = Query(default=10, ge=1, le=50),
    db_session = Depends(get_db_session)
):
    """Get trending issues across all reviews."""
    try:
        metrics_service = MetricsService(db_session)
        trending = await metrics_service.get_trending_issues(days, limit)
        return {"trending_issues": trending, "period_days": days}

    except Exception as e:
        logger.error(f"Failed to get trending issues: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@review_router.get("/metrics/comparison/{review_id1}/{review_id2}")
async def get_comparison_metrics(
    review_id1: str,
    review_id2: str,
    db_session = Depends(get_db_session)
):
    """Get detailed comparison metrics between two reviews."""
    try:
        metrics_service = MetricsService(db_session)
        comparison = await metrics_service.get_comparison_metrics(review_id1, review_id2)
        return comparison

    except Exception as e:
        logger.error(f"Failed to get comparison metrics: {str(e)}")
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