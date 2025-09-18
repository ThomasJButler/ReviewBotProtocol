"""Tests for GitHub webhook endpoints."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
import json
import hmac
import hashlib
from datetime import datetime


class TestWebhookEndpoints:
    """Test GitHub webhook processing."""

    def create_webhook_signature(self, payload: bytes, secret: str) -> str:
        """Create a valid GitHub webhook signature."""
        signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    def test_webhook_missing_headers(self, client: TestClient):
        """Test webhook request missing required headers."""
        response = client.post("/webhook/github", json={"test": "data"})
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_webhook_invalid_signature(self, client: TestClient):
        """Test webhook with invalid signature."""
        payload = json.dumps({"test": "data"}).encode('utf-8')
        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "sha256=invalid_signature",
            "X-GitHub-Delivery": "test-delivery-id"
        }

        response = client.post(
            "/webhook/github",
            content=payload,
            headers=headers
        )
        assert response.status_code == 401

    def test_webhook_valid_signature(self, client: TestClient, sample_pr_data):
        """Test webhook with valid signature."""
        payload = json.dumps(sample_pr_data).encode('utf-8')
        signature = self.create_webhook_signature(payload, "test-webhook-secret")

        headers = {
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "test-delivery-id",
            "Content-Type": "application/json"
        }

        with patch('handlers.webhook.process_webhook_event') as mock_process:
            response = client.post(
                "/webhook/github",
                content=payload,
                headers=headers
            )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["delivery_id"] == "test-delivery-id"

    def test_webhook_invalid_json(self, client: TestClient):
        """Test webhook with invalid JSON payload."""
        payload = b"invalid json content"
        signature = self.create_webhook_signature(payload, "test-webhook-secret")

        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "test-delivery-id"
        }

        response = client.post(
            "/webhook/github",
            content=payload,
            headers=headers
        )
        assert response.status_code == 400

    @patch('handlers.webhook.process_webhook_event')
    def test_pull_request_webhook_processing(self, mock_process, client: TestClient, sample_pr_data):
        """Test processing of pull request webhook events."""
        payload = json.dumps(sample_pr_data).encode('utf-8')
        signature = self.create_webhook_signature(payload, "test-webhook-secret")

        headers = {
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "test-delivery-id"
        }

        response = client.post(
            "/webhook/github",
            content=payload,
            headers=headers
        )

        assert response.status_code == 200
        mock_process.assert_called_once()

    def test_unsupported_webhook_event(self, client: TestClient):
        """Test handling of unsupported webhook events."""
        payload = json.dumps({"action": "created"}).encode('utf-8')
        signature = self.create_webhook_signature(payload, "test-webhook-secret")

        headers = {
            "X-GitHub-Event": "issues",  # Unsupported event
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "test-delivery-id"
        }

        response = client.post(
            "/webhook/github",
            content=payload,
            headers=headers
        )

        # Should accept but not process
        assert response.status_code == 200

    def test_webhook_large_payload(self, client: TestClient):
        """Test webhook with large payload."""
        large_data = {
            "action": "opened",
            "large_field": "x" * 10000  # 10KB of data
        }
        payload = json.dumps(large_data).encode('utf-8')
        signature = self.create_webhook_signature(payload, "test-webhook-secret")

        headers = {
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "test-delivery-id"
        }

        response = client.post(
            "/webhook/github",
            content=payload,
            headers=headers
        )

        # Should handle large payloads
        assert response.status_code in [200, 413]  # 413 if payload too large


class TestWebhookSecurity:
    """Test webhook security features."""

    def test_signature_verification_algorithm(self, client: TestClient):
        """Test that only SHA256 signatures are accepted."""
        payload = json.dumps({"test": "data"}).encode('utf-8')

        # Test with SHA1 (should be rejected)
        sha1_signature = hmac.new(
            b"test-webhook-secret",
            payload,
            hashlib.sha1
        ).hexdigest()

        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature": f"sha1={sha1_signature}",  # Old format
            "X-GitHub-Delivery": "test-delivery-id"
        }

        response = client.post("/webhook/github", content=payload, headers=headers)
        assert response.status_code == 400

    def test_timing_attack_protection(self, client: TestClient):
        """Test that signature comparison is timing-safe."""
        payload = json.dumps({"test": "data"}).encode('utf-8')

        # Test multiple invalid signatures - timing should be consistent
        invalid_signatures = [
            "sha256=invalid1",
            "sha256=invalid2",
            "sha256=completely_different_length_signature"
        ]

        times = []
        for sig in invalid_signatures:
            headers = {
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "test-delivery-id"
            }

            import time
            start = time.time()
            response = client.post("/webhook/github", content=payload, headers=headers)
            end = time.time()

            assert response.status_code == 401
            times.append(end - start)

        # Times should be relatively consistent (within reasonable bounds)
        avg_time = sum(times) / len(times)
        for t in times:
            assert abs(t - avg_time) < 0.1  # Within 100ms variance

    def test_empty_secret_handling(self, client: TestClient):
        """Test handling when webhook secret is not configured."""
        with patch('config.settings.settings.GITHUB_WEBHOOK_SECRET', ''):
            payload = json.dumps({"test": "data"}).encode('utf-8')
            headers = {
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": "sha256=anything",
                "X-GitHub-Delivery": "test-delivery-id"
            }

            response = client.post("/webhook/github", content=payload, headers=headers)
            assert response.status_code == 401


class TestWebhookProcessing:
    """Test webhook event processing logic."""

    @patch('services.github_client.GitHubClient')
    @patch('services.ai_reviewer.AIReviewService')
    async def test_pull_request_processing(self, mock_ai_service, mock_github_client, sample_pr_data):
        """Test pull request webhook processing."""
        from handlers.webhook import handle_pull_request_event

        # Mock GitHub client
        mock_github_instance = MagicMock()
        mock_github_client.return_value = mock_github_instance
        mock_github_instance.get_pr_files = AsyncMock(return_value=[
            {
                "filename": "test.py",
                "patch": "diff content",
                "additions": 10,
                "deletions": 5
            }
        ])
        mock_github_instance.post_review_comments = AsyncMock()
        mock_github_instance.create_status_check = AsyncMock()

        # Mock AI service
        mock_ai_instance = MagicMock()
        mock_ai_service.return_value = mock_ai_instance
        mock_ai_instance.review_pull_request = AsyncMock(return_value={
            "score": 8,
            "summary": "Good code quality",
            "comments": [],
            "issues": []
        })

        # Process the webhook
        await handle_pull_request_event(sample_pr_data, "test-delivery-id")

        # Verify methods were called
        mock_github_instance.get_pr_files.assert_called_once()
        mock_ai_instance.review_pull_request.assert_called_once()

    async def test_ignored_pr_actions(self, sample_pr_data):
        """Test that certain PR actions are ignored."""
        from handlers.webhook import handle_pull_request_event

        ignored_actions = ["closed", "edited", "labeled"]

        for action in ignored_actions:
            test_data = sample_pr_data.copy()
            test_data["action"] = action

            # Should not raise an error, but should not process
            with patch('services.github_client.GitHubClient') as mock_client:
                await handle_pull_request_event(test_data, "test-delivery-id")
                mock_client.assert_not_called()

    async def test_missing_installation_id(self, sample_pr_data):
        """Test handling of webhook without installation ID."""
        from handlers.webhook import handle_pull_request_event

        # Remove installation from payload
        test_data = sample_pr_data.copy()
        del test_data["installation"]

        # Should handle gracefully
        await handle_pull_request_event(test_data, "test-delivery-id")

    @patch('services.github_client.GitHubClient')
    async def test_too_many_files_in_pr(self, mock_github_client, sample_pr_data):
        """Test handling when PR has too many files."""
        from handlers.webhook import handle_pull_request_event

        # Mock GitHub client to return many files
        mock_github_instance = MagicMock()
        mock_github_client.return_value = mock_github_instance
        mock_github_instance.get_pr_files = AsyncMock(return_value=[
            {"filename": f"file_{i}.py"} for i in range(200)  # More than MAX_FILES_PER_PR
        ])

        await handle_pull_request_event(sample_pr_data, "test-delivery-id")

        # Should call get_pr_files but not proceed with review
        mock_github_instance.get_pr_files.assert_called_once()
        mock_github_instance.post_review_comments.assert_not_called()


class TestWebhookErrorHandling:
    """Test error handling in webhook processing."""

    def test_webhook_exception_handling(self, client: TestClient):
        """Test that webhook exceptions are handled gracefully."""
        payload = json.dumps({"test": "data"}).encode('utf-8')
        signature = hmac.new(
            b"test-webhook-secret",
            payload,
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": f"sha256={signature}",
            "X-GitHub-Delivery": "test-delivery-id"
        }

        with patch('handlers.webhook.process_webhook_event', side_effect=Exception("Test error")):
            response = client.post("/webhook/github", content=payload, headers=headers)

        # Should return success even if background processing fails
        assert response.status_code == 200

    @patch('handlers.webhook.logger')
    async def test_error_logging(self, mock_logger, sample_pr_data):
        """Test that errors are properly logged."""
        from handlers.webhook import handle_pull_request_event

        with patch('services.github_client.GitHubClient', side_effect=Exception("GitHub API error")):
            await handle_pull_request_event(sample_pr_data, "test-delivery-id")

        # Should log the error
        mock_logger.error.assert_called()


@pytest.mark.asyncio
class TestAsyncWebhookProcessing:
    """Test async webhook processing."""

    async def test_concurrent_webhook_processing(self, async_client: AsyncClient):
        """Test that multiple webhooks can be processed concurrently."""
        import asyncio

        payload = json.dumps({"action": "opened"}).encode('utf-8')
        signature = hmac.new(
            b"test-webhook-secret",
            payload,
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": f"sha256={signature}",
            "X-GitHub-Delivery": "test-delivery-id"
        }

        # Send multiple webhooks concurrently
        async def send_webhook():
            return await async_client.post("/webhook/github", content=payload, headers=headers)

        tasks = [send_webhook() for _ in range(3)]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == 200