"""
GitHub metrics aggregation service for review analytics
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
import logging

from database.models import Review, User
from database.repositories.review_repository import ReviewRepository
from utils.datetime_utils import get_utc_timestamp

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for aggregating and analyzing review metrics"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.review_repo = ReviewRepository(db_session)

    async def get_user_metrics(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get comprehensive metrics for a user"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # Get all reviews for the user in the time period
            reviews = await self.review_repo.get_filtered_reviews(
                filters={"created_by": user_id},
                start_date=start_date,
                limit=1000
            )

            # Calculate metrics
            total_reviews = len(reviews)
            completed_reviews = [r for r in reviews if r.status == "completed"]
            failed_reviews = [r for r in reviews if r.status == "failed"]

            # Extract scores and issues
            scores = []
            total_issues = 0
            critical_issues = 0
            high_issues = 0
            medium_issues = 0
            low_issues = 0
            security_issues = 0
            performance_issues = 0
            quality_issues = 0
            lines_analyzed = 0
            files_analyzed = 0

            for review in completed_reviews:
                if review.results:
                    # Score metrics
                    if "overall_score" in review.results:
                        scores.append(review.results["overall_score"])

                    # Issue counts
                    if "total_issues" in review.results:
                        total_issues += review.results["total_issues"]
                    if "critical_issues" in review.results:
                        critical_issues += review.results["critical_issues"]
                    if "high_issues" in review.results:
                        high_issues += review.results["high_issues"]
                    if "medium_issues" in review.results:
                        medium_issues += review.results["medium_issues"]
                    if "low_issues" in review.results:
                        low_issues += review.results["low_issues"]

                    # Category-specific issues
                    if "security_issues" in review.results:
                        security_issues += len(review.results["security_issues"])
                    if "performance_issues" in review.results:
                        performance_issues += len(review.results["performance_issues"])
                    if "quality_issues" in review.results:
                        quality_issues += len(review.results["quality_issues"])

                    # Code metrics
                    if "lines_analyzed" in review.results:
                        lines_analyzed += review.results["lines_analyzed"]
                    if "files_analyzed" in review.results:
                        files_analyzed += review.results["files_analyzed"]

            # Calculate averages
            avg_score = sum(scores) / len(scores) if scores else 0
            avg_issues_per_review = total_issues / len(completed_reviews) if completed_reviews else 0

            # Calculate trend (compare last 7 days to previous 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_reviews = [r for r in reviews if r.created_at >= week_ago]
            older_reviews = [r for r in reviews if r.created_at < week_ago]

            recent_scores = []
            older_scores = []

            for review in recent_reviews:
                if review.results and "overall_score" in review.results:
                    recent_scores.append(review.results["overall_score"])

            for review in older_reviews:
                if review.results and "overall_score" in review.results:
                    older_scores.append(review.results["overall_score"])

            recent_avg = sum(recent_scores) / len(recent_scores) if recent_scores else 0
            older_avg = sum(older_scores) / len(older_scores) if older_scores else 0
            score_trend = recent_avg - older_avg

            # Repository breakdown
            repository_stats = {}
            for review in reviews:
                if review.repository:
                    if review.repository not in repository_stats:
                        repository_stats[review.repository] = {
                            "count": 0,
                            "total_score": 0,
                            "issues": 0
                        }
                    repository_stats[review.repository]["count"] += 1
                    if review.results:
                        if "overall_score" in review.results:
                            repository_stats[review.repository]["total_score"] += review.results["overall_score"]
                        if "total_issues" in review.results:
                            repository_stats[review.repository]["issues"] += review.results["total_issues"]

            # Calculate repository averages
            for repo_name, stats in repository_stats.items():
                if stats["count"] > 0:
                    stats["avg_score"] = stats["total_score"] / stats["count"]

            # Top repositories by review count
            top_repositories = sorted(
                repository_stats.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:5]

            # Activity heatmap data (by day of week and hour)
            activity_heatmap = self._calculate_activity_heatmap(reviews)

            # Review type breakdown
            review_types = {
                "paste": len([r for r in reviews if r.type == "paste"]),
                "upload": len([r for r in reviews if r.type == "upload"]),
                "github_pr": len([r for r in reviews if r.type == "github_pr"])
            }

            # Success rate
            success_rate = (len(completed_reviews) / total_reviews * 100) if total_reviews > 0 else 0

            return {
                "user_id": user_id,
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": datetime.utcnow().isoformat(),
                "summary": {
                    "total_reviews": total_reviews,
                    "completed_reviews": len(completed_reviews),
                    "failed_reviews": len(failed_reviews),
                    "success_rate": round(success_rate, 1),
                    "avg_score": round(avg_score, 1),
                    "avg_issues_per_review": round(avg_issues_per_review, 1),
                    "score_trend": round(score_trend, 1),
                    "total_lines_analyzed": lines_analyzed,
                    "total_files_analyzed": files_analyzed
                },
                "issues": {
                    "total": total_issues,
                    "critical": critical_issues,
                    "high": high_issues,
                    "medium": medium_issues,
                    "low": low_issues,
                    "by_category": {
                        "security": security_issues,
                        "performance": performance_issues,
                        "quality": quality_issues
                    }
                },
                "review_types": review_types,
                "top_repositories": [
                    {
                        "name": repo,
                        "count": stats["count"],
                        "avg_score": round(stats.get("avg_score", 0), 1),
                        "total_issues": stats["issues"]
                    }
                    for repo, stats in top_repositories
                ],
                "activity_heatmap": activity_heatmap,
                "recent_activity": await self._get_recent_activity(user_id, 7)
            }

        except Exception as e:
            logger.error(f"Error calculating user metrics: {str(e)}")
            return {
                "error": "Failed to calculate metrics",
                "user_id": user_id,
                "period_days": days
            }

    async def get_repository_metrics(
        self,
        repository: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get metrics for a specific repository"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # Get all reviews for the repository
            reviews = await self.review_repo.get_filtered_reviews(
                filters={"repository": repository},
                start_date=start_date,
                limit=1000
            )

            completed_reviews = [r for r in reviews if r.status == "completed"]

            # Calculate metrics similar to user metrics but for repository
            scores = []
            issues_by_file = {}
            contributors = set()

            for review in completed_reviews:
                if review.created_by:
                    contributors.add(review.created_by)

                if review.results:
                    if "overall_score" in review.results:
                        scores.append(review.results["overall_score"])

                    # Track issues by file
                    for issue_type in ["security_issues", "performance_issues", "quality_issues"]:
                        if issue_type in review.results:
                            for issue in review.results[issue_type]:
                                if "file" in issue:
                                    file_name = issue["file"]
                                    if file_name not in issues_by_file:
                                        issues_by_file[file_name] = []
                                    issues_by_file[file_name].append({
                                        "type": issue_type.replace("_issues", ""),
                                        "severity": issue.get("severity", "medium"),
                                        "line": issue.get("line_number")
                                    })

            avg_score = sum(scores) / len(scores) if scores else 0

            # Find most problematic files
            problematic_files = sorted(
                [(f, len(issues)) for f, issues in issues_by_file.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]

            return {
                "repository": repository,
                "period_days": days,
                "total_reviews": len(reviews),
                "completed_reviews": len(completed_reviews),
                "avg_score": round(avg_score, 1),
                "unique_contributors": len(contributors),
                "problematic_files": [
                    {"file": f, "issue_count": count}
                    for f, count in problematic_files
                ],
                "health_score": self._calculate_health_score(completed_reviews)
            }

        except Exception as e:
            logger.error(f"Error calculating repository metrics: {str(e)}")
            return {
                "error": "Failed to calculate repository metrics",
                "repository": repository
            }

    async def get_comparison_metrics(
        self,
        review_id1: str,
        review_id2: str
    ) -> Dict[str, Any]:
        """Compare two reviews"""
        try:
            review1 = await self.review_repo.get_by_id(review_id1)
            review2 = await self.review_repo.get_by_id(review_id2)

            if not review1 or not review2:
                return {"error": "One or both reviews not found"}

            # Extract metrics from both reviews
            def extract_metrics(review):
                if not review.results:
                    return {}

                return {
                    "score": review.results.get("overall_score", 0),
                    "grade": review.results.get("letter_grade", "N/A"),
                    "total_issues": review.results.get("total_issues", 0),
                    "critical_issues": review.results.get("critical_issues", 0),
                    "security_issues": len(review.results.get("security_issues", [])),
                    "performance_issues": len(review.results.get("performance_issues", [])),
                    "quality_issues": len(review.results.get("quality_issues", [])),
                    "lines_analyzed": review.results.get("lines_analyzed", 0),
                    "complexity": review.results.get("complexity_score", 0)
                }

            metrics1 = extract_metrics(review1)
            metrics2 = extract_metrics(review2)

            # Calculate improvements
            improvements = {}
            for key in metrics1:
                if key in metrics2:
                    if key in ["score", "grade"]:
                        # Higher is better
                        diff = metrics2[key] - metrics1[key] if isinstance(metrics1[key], (int, float)) else None
                    else:
                        # Lower is better for issues
                        diff = metrics1[key] - metrics2[key] if isinstance(metrics1[key], (int, float)) else None

                    if diff is not None:
                        improvements[key] = {
                            "review1": metrics1[key],
                            "review2": metrics2[key],
                            "change": diff,
                            "percent_change": (diff / metrics1[key] * 100) if metrics1[key] > 0 else 0
                        }

            return {
                "review1": {
                    "id": review1.id,
                    "created_at": review1.created_at.isoformat(),
                    "repository": review1.repository,
                    "metrics": metrics1
                },
                "review2": {
                    "id": review2.id,
                    "created_at": review2.created_at.isoformat(),
                    "repository": review2.repository,
                    "metrics": metrics2
                },
                "improvements": improvements,
                "overall_improvement": self._calculate_overall_improvement(metrics1, metrics2)
            }

        except Exception as e:
            logger.error(f"Error comparing reviews: {str(e)}")
            return {"error": "Failed to compare reviews"}

    async def get_trending_issues(
        self,
        days: int = 7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get trending issues across all reviews"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # Get recent reviews
            stmt = select(Review).where(
                and_(
                    Review.created_at >= start_date,
                    Review.status == "completed"
                )
            ).limit(100)

            result = await self.db_session.execute(stmt)
            reviews = result.scalars().all()

            # Aggregate issues
            issue_counts = {}

            for review in reviews:
                if review.results:
                    for issue_type in ["security_issues", "performance_issues", "quality_issues"]:
                        if issue_type in review.results:
                            for issue in review.results[issue_type]:
                                issue_key = f"{issue.get('type', 'unknown')}:{issue.get('title', 'unknown')}"
                                if issue_key not in issue_counts:
                                    issue_counts[issue_key] = {
                                        "type": issue.get("type"),
                                        "title": issue.get("title"),
                                        "category": issue_type.replace("_issues", ""),
                                        "severity": issue.get("severity", "medium"),
                                        "count": 0,
                                        "repositories": set()
                                    }
                                issue_counts[issue_key]["count"] += 1
                                if review.repository:
                                    issue_counts[issue_key]["repositories"].add(review.repository)

            # Sort by count and convert sets to lists
            trending = sorted(issue_counts.values(), key=lambda x: x["count"], reverse=True)[:limit]
            for issue in trending:
                issue["repositories"] = list(issue["repositories"])

            return trending

        except Exception as e:
            logger.error(f"Error getting trending issues: {str(e)}")
            return []

    def _calculate_activity_heatmap(self, reviews: List[Review]) -> Dict[str, Any]:
        """Calculate activity heatmap data"""
        heatmap = {}

        for review in reviews:
            if review.created_at:
                day = review.created_at.strftime("%A")
                hour = review.created_at.hour

                if day not in heatmap:
                    heatmap[day] = {}
                if hour not in heatmap[day]:
                    heatmap[day][hour] = 0
                heatmap[day][hour] += 1

        return heatmap

    async def _get_recent_activity(self, user_id: str, days: int) -> List[Dict[str, Any]]:
        """Get recent activity summary"""
        start_date = datetime.utcnow() - timedelta(days=days)

        reviews = await self.review_repo.get_filtered_reviews(
            filters={"created_by": user_id},
            start_date=start_date,
            limit=10,
            sort_by="created_at",
            order="desc"
        )

        activity = []
        for review in reviews:
            activity_item = {
                "id": review.id,
                "timestamp": review.created_at.isoformat(),
                "type": review.type,
                "repository": review.repository,
                "status": review.status
            }

            if review.results:
                activity_item["score"] = review.results.get("overall_score", 0)
                activity_item["issues"] = review.results.get("total_issues", 0)

            activity.append(activity_item)

        return activity

    def _calculate_health_score(self, reviews: List[Review]) -> float:
        """Calculate overall health score for a set of reviews"""
        if not reviews:
            return 0.0

        scores = []
        issue_ratios = []

        for review in reviews:
            if review.results:
                if "overall_score" in review.results:
                    scores.append(review.results["overall_score"])

                lines = review.results.get("lines_analyzed", 0)
                issues = review.results.get("total_issues", 0)
                if lines > 0:
                    # Issues per 100 lines (lower is better)
                    issue_ratios.append((issues / lines) * 100)

        avg_score = sum(scores) / len(scores) if scores else 50
        avg_issue_ratio = sum(issue_ratios) / len(issue_ratios) if issue_ratios else 10

        # Health score formula: 70% from score, 30% from issue ratio (inverted)
        # Issue ratio penalty: subtract up to 30 points based on issues per 100 lines
        issue_penalty = min(30, avg_issue_ratio * 3)  # 3 points per issue per 100 lines
        health_score = (avg_score * 0.7) + (30 - issue_penalty)

        return round(max(0, min(100, health_score)), 1)

    def _calculate_overall_improvement(
        self,
        metrics1: Dict[str, Any],
        metrics2: Dict[str, Any]
    ) -> str:
        """Calculate overall improvement between two reviews"""
        score1 = metrics1.get("score", 0)
        score2 = metrics2.get("score", 0)
        issues1 = metrics1.get("total_issues", 0)
        issues2 = metrics2.get("total_issues", 0)

        score_improvement = score2 - score1
        issue_improvement = issues1 - issues2  # Fewer issues is better

        if score_improvement > 5 or issue_improvement > 3:
            return "significant_improvement"
        elif score_improvement > 0 or issue_improvement > 0:
            return "improvement"
        elif score_improvement == 0 and issue_improvement == 0:
            return "no_change"
        elif score_improvement > -5 and issue_improvement > -3:
            return "slight_regression"
        else:
            return "regression"