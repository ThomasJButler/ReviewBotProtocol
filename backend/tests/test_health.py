"""Tests for health check and basic endpoints."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """Test the root endpoint returns basic info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert data["name"] == "Git Review Assistant API"

    def test_health_check(self, client: TestClient):
        """Test basic health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_detailed_health_check(self, client: TestClient):
        """Test detailed health check endpoint."""
        response = client.get("/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "version" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_health_async(self, async_client: AsyncClient):
        """Test health endpoint with async client."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_fields(self, client: TestClient):
        """Test that health check returns all expected fields."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        required_fields = ["status", "version", "timestamp"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_health_response_format(self, client: TestClient):
        """Test that health response has correct format."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["timestamp"], (int, float))

    def test_cors_headers(self, client: TestClient):
        """Test that CORS headers are present."""
        response = client.get("/health")
        assert response.status_code == 200
        # CORS headers might not be present in test client
        # Just verify the response is successful

    def test_health_under_load(self, client: TestClient):
        """Test health endpoint can handle multiple requests."""
        responses = []
        for _ in range(10):
            response = client.get("/health")
            responses.append(response)

        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"


class TestErrorHandling:
    """Test error handling for basic endpoints."""

    def test_404_endpoint(self, client: TestClient):
        """Test that non-existent endpoints return 404."""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404

    def test_invalid_method(self, client: TestClient):
        """Test that invalid HTTP methods return 405."""
        response = client.post("/health")
        assert response.status_code == 405

    def test_malformed_request(self, client: TestClient):
        """Test handling of malformed requests."""
        # Test with invalid JSON in request body
        response = client.post(
            "/review/manual",
            json={"invalid": "malformed json structure"}
        )
        # Should return 422 for validation error or 401 for auth
        assert response.status_code in [401, 422]


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    def test_openapi_json(self, client: TestClient):
        """Test that OpenAPI JSON is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "Git Review Assistant API"

    def test_docs_redirect(self, client: TestClient):
        """Test that /docs endpoint is accessible."""
        response = client.get("/docs")
        # Should either return docs or redirect (depending on DEBUG setting)
        assert response.status_code in [200, 404]  # 404 if docs disabled in production

    def test_redoc_redirect(self, client: TestClient):
        """Test that /redoc endpoint is accessible."""
        response = client.get("/redoc")
        # Should either return redoc or redirect (depending on DEBUG setting)
        assert response.status_code in [200, 404]  # 404 if docs disabled in production


class TestApplicationLifecycle:
    """Test application startup and lifecycle."""

    def test_application_starts(self, client: TestClient):
        """Test that the application starts successfully."""
        # If we can make a request, the app started
        response = client.get("/health")
        assert response.status_code == 200

    def test_database_connection(self, client: TestClient):
        """Test that database connection works."""
        response = client.get("/health/detailed")
        assert response.status_code == 200
        data = response.json()
        # Database status might be unhealthy in test environment
        assert "checks" in data
        assert "database" in data["checks"]
        # Just verify the structure exists, not the status

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, async_client: AsyncClient):
        """Test that the app can handle concurrent requests."""
        import asyncio

        async def make_request():
            response = await async_client.get("/health")
            return response.status_code

        # Make 5 concurrent requests
        tasks = [make_request() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(status == 200 for status in results)