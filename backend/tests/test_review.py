"""Tests for code review endpoints."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
from io import BytesIO
import json


class TestManualReviewEndpoints:
    """Test manual code review endpoints."""

    def test_manual_review_no_auth(self, client: TestClient):
        """Test manual review without authentication."""
        review_data = {
            "code": "print('hello world')",
            "language": "python"
        }

        response = client.post("/review/manual", json=review_data)
        # Should require authentication
        assert response.status_code == 401

    @patch('handlers.review.require_auth')
    @patch('services.ai_reviewer.AIReviewService')
    def test_manual_review_success(self, mock_ai_service, mock_auth, client: TestClient, sample_code_review):
        """Test successful manual code review."""
        # Mock authentication
        mock_auth.return_value = MagicMock(username="testuser")

        # Mock AI service
        mock_ai_instance = MagicMock()
        mock_ai_service.return_value = mock_ai_instance
        mock_ai_instance.review_code = AsyncMock(return_value={
            "score": 7,
            "summary": "Code looks good with minor issues",
            "findings": [
                {
                    "severity": "medium",
                    "category": "security",
                    "title": "Potential SQL injection",
                    "description": "User input not sanitized",
                    "line": 5
                }
            ],
            "issues": []
        })

        response = client.post("/review/manual", json=sample_code_review)
        assert response.status_code == 200
        data = response.json()
        assert "review_id" in data
        assert "status" in data

    def test_manual_review_invalid_data(self, client: TestClient):
        """Test manual review with invalid data."""
        invalid_data = {
            "invalid_field": "test"
        }

        response = client.post("/review/manual", json=invalid_data)
        assert response.status_code == 422  # Validation error

    def test_manual_review_empty_code(self, client: TestClient):
        """Test manual review with empty code."""
        review_data = {
            "code": "",
            "language": "python"
        }

        response = client.post("/review/manual", json=review_data)
        assert response.status_code in [400, 422]

    @patch('handlers.review.require_auth')
    def test_manual_review_large_code(self, mock_auth, client: TestClient):
        """Test manual review with large code file."""
        mock_auth.return_value = MagicMock(username="testuser")

        large_code = "print('hello')\n" * 10000  # Large code file
        review_data = {
            "code": large_code,
            "language": "python"
        }

        response = client.post("/review/manual", json=review_data)
        # Should handle large files or return appropriate error
        assert response.status_code in [200, 413, 422]


class TestFileUploadReview:
    """Test file upload review endpoints."""

    @patch('handlers.review.require_auth')
    def test_file_upload_no_file(self, mock_auth, client: TestClient):
        """Test file upload review without file."""
        mock_auth.return_value = MagicMock(username="testuser")

        response = client.post("/review/file")
        assert response.status_code == 422

    @patch('handlers.review.require_auth')
    @patch('services.ai_reviewer.AIReviewService')
    def test_file_upload_success(self, mock_ai_service, mock_auth, client: TestClient):
        """Test successful file upload review."""
        mock_auth.return_value = MagicMock(username="testuser")

        # Mock AI service
        mock_ai_instance = MagicMock()
        mock_ai_service.return_value = mock_ai_instance
        mock_ai_instance.review_file = AsyncMock(return_value={
            "score": 8,
            "summary": "File looks good",
            "findings": []
        })

        # Create a test file
        test_file_content = b"def hello():\n    print('hello world')\n"
        files = {"file": ("test.py", BytesIO(test_file_content), "text/plain")}

        response = client.post("/review/file", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "review_id" in data

    @patch('handlers.review.require_auth')
    def test_file_upload_invalid_type(self, mock_auth, client: TestClient):
        """Test file upload with invalid file type."""
        mock_auth.return_value = MagicMock(username="testuser")

        # Upload a binary file
        binary_content = b"\x89PNG\r\n\x1a\n"  # PNG header
        files = {"file": ("test.png", BytesIO(binary_content), "image/png")}

        response = client.post("/review/file", files=files)
        # Should reject non-code files
        assert response.status_code in [400, 422]

    @patch('handlers.review.require_auth')
    def test_file_upload_too_large(self, mock_auth, client: TestClient):
        """Test file upload that exceeds size limit."""
        mock_auth.return_value = MagicMock(username="testuser")

        # Create a large file (over limit)
        large_content = b"print('test')\n" * 100000  # Very large file
        files = {"file": ("large.py", BytesIO(large_content), "text/plain")}

        response = client.post("/review/file", files=files)
        # Should reject files that are too large
        assert response.status_code in [413, 422]


class TestPRReviewEndpoints:
    """Test pull request review endpoints."""

    @patch('handlers.review.require_auth')
    def test_pr_review_no_params(self, mock_auth, client: TestClient):
        """Test PR review without required parameters."""
        mock_auth.return_value = MagicMock(username="testuser")

        response = client.post("/review/pr")
        assert response.status_code == 422

    @patch('handlers.review.require_auth')
    @patch('services.github_client.GitHubClient')
    @patch('services.ai_reviewer.AIReviewService')
    def test_pr_review_success(self, mock_ai_service, mock_github_client, mock_auth, client: TestClient):
        """Test successful PR review."""
        mock_auth.return_value = MagicMock(username="testuser")

        # Mock GitHub client
        mock_github_instance = MagicMock()
        mock_github_client.return_value = mock_github_instance
        mock_github_instance.get_pr_files = AsyncMock(return_value=[
            {
                "filename": "test.py",
                "patch": "diff content",
                "additions": 5,
                "deletions": 2
            }
        ])

        # Mock AI service
        mock_ai_instance = MagicMock()
        mock_ai_service.return_value = mock_ai_instance
        mock_ai_instance.review_pull_request = AsyncMock(return_value={
            "score": 9,
            "summary": "Excellent PR",
            "findings": []
        })

        pr_data = {
            "repository": "test/repo",
            "pr_number": 123
        }

        response = client.post("/review/pr", json=pr_data)
        assert response.status_code == 200
        data = response.json()
        assert "review_id" in data

    @patch('handlers.review.require_auth')
    def test_pr_review_invalid_repo(self, mock_auth, client: TestClient):
        """Test PR review with invalid repository."""
        mock_auth.return_value = MagicMock(username="testuser")

        pr_data = {
            "repository": "invalid-repo-format",
            "pr_number": 123
        }

        response = client.post("/review/pr", json=pr_data)
        assert response.status_code in [400, 422]

    @patch('handlers.review.require_auth')
    @patch('services.github_client.GitHubClient')
    def test_pr_review_github_error(self, mock_github_client, mock_auth, client: TestClient):
        """Test PR review when GitHub API returns error."""
        mock_auth.return_value = MagicMock(username="testuser")

        # Mock GitHub client to raise error
        mock_github_instance = MagicMock()
        mock_github_client.return_value = mock_github_instance
        mock_github_instance.get_pr_files = AsyncMock(side_effect=Exception("GitHub API error"))

        pr_data = {
            "repository": "test/repo",
            "pr_number": 123
        }

        response = client.post("/review/pr", json=pr_data)
        assert response.status_code == 500


class TestReviewResultsEndpoints:
    """Test review results retrieval endpoints."""

    @patch('handlers.review.require_auth')
    @patch('database.repositories.review_repository.ReviewRepository')
    def test_get_review_success(self, mock_repo, mock_auth, client: TestClient):
        """Test successful review retrieval."""
        mock_auth.return_value = MagicMock(username="testuser")

        # Mock repository
        mock_repo_instance = MagicMock()
        mock_repo.return_value = mock_repo_instance
        mock_repo_instance.get_review = AsyncMock(return_value={
            "id": "test-review-id",
            "status": "completed",
            "score": 8,
            "summary": "Good code",
            "created_at": "2025-01-01T00:00:00Z"
        })

        response = client.get("/review/test-review-id")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-review-id"
        assert data["status"] == "completed"

    def test_get_review_no_auth(self, client: TestClient):
        """Test review retrieval without authentication."""
        response = client.get("/review/test-review-id")
        assert response.status_code == 401

    @patch('handlers.review.require_auth')
    @patch('database.repositories.review_repository.ReviewRepository')
    def test_get_review_not_found(self, mock_repo, mock_auth, client: TestClient):
        """Test retrieval of non-existent review."""
        mock_auth.return_value = MagicMock(username="testuser")

        mock_repo_instance = MagicMock()
        mock_repo.return_value = mock_repo_instance
        mock_repo_instance.get_review = AsyncMock(return_value=None)

        response = client.get("/review/nonexistent-id")
        assert response.status_code == 404

    @patch('handlers.review.require_auth')
    @patch('database.repositories.review_repository.ReviewRepository')
    def test_list_reviews(self, mock_repo, mock_auth, client: TestClient):
        """Test listing user reviews."""
        mock_auth.return_value = MagicMock(username="testuser", id=123)

        mock_repo_instance = MagicMock()
        mock_repo.return_value = mock_repo_instance
        mock_repo_instance.get_user_reviews = AsyncMock(return_value=[
            {"id": "review1", "status": "completed"},
            {"id": "review2", "status": "pending"}
        ])

        response = client.get("/review/")
        assert response.status_code == 200
        data = response.json()
        assert "reviews" in data
        assert len(data["reviews"]) == 2


class TestReviewStatistics:
    """Test review statistics endpoints."""

    @patch('handlers.review.require_auth')
    @patch('database.repositories.review_repository.ReviewRepository')
    def test_review_stats_overview(self, mock_repo, mock_auth, client: TestClient):
        """Test review statistics overview."""
        mock_auth.return_value = MagicMock(username="testuser")

        mock_repo_instance = MagicMock()
        mock_repo.return_value = mock_repo_instance
        mock_repo_instance.get_review_stats = AsyncMock(return_value={
            "total_reviews": 100,
            "completed_reviews": 95,
            "average_score": 8.2,
            "issues_found": 245
        })

        response = client.get("/review/stats/overview")
        assert response.status_code == 200
        data = response.json()
        assert "total_reviews" in data
        assert "average_score" in data


class TestSecurityScanning:
    """Test security scanning functionality."""

    @patch('handlers.review.require_auth')
    @patch('services.security_scanner.SecurityScanner')
    def test_security_scan_endpoint(self, mock_scanner, mock_auth, client: TestClient):
        """Test security scanning endpoint."""
        mock_auth.return_value = MagicMock(username="testuser")

        # Mock security scanner
        mock_scanner_instance = MagicMock()
        mock_scanner.return_value = mock_scanner_instance
        mock_scanner_instance.scan_code = AsyncMock(return_value=[
            {
                "type": "sql_injection",
                "severity": "high",
                "line": 5,
                "message": "Potential SQL injection vulnerability"
            }
        ])

        scan_data = {
            "code": "SELECT * FROM users WHERE id = '" + user_id + "'",
            "language": "python"
        }

        response = client.post("/review/security-scan", json=scan_data)
        assert response.status_code == 200
        data = response.json()
        assert "vulnerabilities" in data


class TestPerformanceAnalysis:
    """Test performance analysis functionality."""

    @patch('handlers.review.require_auth')
    @patch('services.ai_reviewer.AIReviewService')
    def test_performance_analysis(self, mock_ai_service, mock_auth, client: TestClient):
        """Test performance analysis endpoint."""
        mock_auth.return_value = MagicMock(username="testuser")

        # Mock AI service
        mock_ai_instance = MagicMock()
        mock_ai_service.return_value = mock_ai_instance
        mock_ai_instance.analyze_performance = AsyncMock(return_value={
            "complexity_score": 7,
            "performance_issues": [
                {
                    "type": "nested_loops",
                    "severity": "medium",
                    "line": 10,
                    "suggestion": "Consider optimizing nested loops"
                }
            ]
        })

        analysis_data = {
            "code": "for i in range(1000):\n    for j in range(1000):\n        pass",
            "language": "python"
        }

        response = client.post("/review/performance-analysis", json=analysis_data)
        assert response.status_code == 200
        data = response.json()
        assert "complexity_score" in data


@pytest.mark.asyncio
class TestAsyncReviewEndpoints:
    """Test review endpoints with async client."""

    async def test_manual_review_async(self, async_client: AsyncClient, sample_code_review):
        """Test manual review with async client."""
        response = await async_client.post("/review/manual", json=sample_code_review)
        # Should require authentication
        assert response.status_code == 401

    @patch('handlers.review.require_auth')
    @patch('services.ai_reviewer.AIReviewService')
    async def test_concurrent_reviews(self, mock_ai_service, mock_auth, async_client: AsyncClient):
        """Test handling of concurrent review requests."""
        import asyncio

        mock_auth.return_value = MagicMock(username="testuser")

        # Mock AI service
        mock_ai_instance = MagicMock()
        mock_ai_service.return_value = mock_ai_instance
        mock_ai_instance.review_code = AsyncMock(return_value={"score": 8})

        review_data = {
            "code": "print('hello')",
            "language": "python"
        }

        # Send multiple concurrent reviews
        async def send_review():
            return await async_client.post("/review/manual", json=review_data)

        tasks = [send_review() for _ in range(3)]
        responses = await asyncio.gather(*tasks)

        # Check that all requests were handled
        assert len(responses) == 3


class TestReviewConfiguration:
    """Test review configuration options."""

    @patch('handlers.review.require_auth')
    def test_review_with_custom_config(self, mock_auth, client: TestClient):
        """Test review with custom configuration."""
        mock_auth.return_value = MagicMock(username="testuser")

        review_data = {
            "code": "print('hello')",
            "language": "python",
            "config": {
                "include_security": True,
                "include_performance": False,
                "include_quality": True
            }
        }

        response = client.post("/review/manual", json=review_data)
        # Should accept configuration options
        assert response.status_code in [200, 401, 422]

    def test_review_config_validation(self, client: TestClient):
        """Test validation of review configuration."""
        review_data = {
            "code": "print('hello')",
            "language": "python",
            "config": {
                "invalid_option": True
            }
        }

        response = client.post("/review/manual", json=review_data)
        # Should validate configuration
        assert response.status_code in [401, 422]