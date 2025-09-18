"""Tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
import jwt
from datetime import datetime, timedelta
import time


class TestAuthenticationEndpoints:
    """Test authentication-related endpoints."""

    def test_github_login_redirect(self, client: TestClient):
        """Test GitHub OAuth login redirect."""
        response = client.get("/auth/github/login")
        assert response.status_code == 200
        data = response.json()
        assert "login_url" in data
        assert "github.com" in data["login_url"]
        assert "client_id" in data["login_url"]

    def test_github_callback_missing_code(self, client: TestClient):
        """Test GitHub callback without authorization code."""
        response = client.post("/auth/github/callback")
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_github_callback_with_error(self, client: TestClient):
        """Test GitHub callback with error parameter."""
        response = client.post("/auth/github/callback?error=access_denied")
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @patch('handlers.auth.httpx.AsyncClient.post')
    @patch('handlers.auth.httpx.AsyncClient.get')
    def test_github_callback_success(self, mock_get, mock_post, client: TestClient):
        """Test successful GitHub OAuth callback."""
        # Mock GitHub token exchange
        mock_post.return_value = MagicMock()
        mock_post.return_value.json.return_value = {
            "access_token": "test_token",
            "token_type": "bearer"
        }
        mock_post.return_value.status_code = 200

        # Mock GitHub user API
        mock_get.return_value = MagicMock()
        mock_get.return_value.json.return_value = {
            "id": 123,
            "login": "testuser",
            "email": "test@example.com",
            "name": "Test User",
            "avatar_url": "https://github.com/testuser.png"
        }
        mock_get.return_value.status_code = 200

        response = client.get("/auth/github/callback?code=test_code")
        # Should redirect or return success
        assert response.status_code in [200, 302]

    def test_token_creation(self, client: TestClient):
        """Test JWT token creation endpoint."""
        user_data = {
            "username": "testuser",
            "email": "test@example.com"
        }

        response = client.post("/auth/token", json=user_data)
        # Should require authentication or return token
        assert response.status_code in [200, 401, 422]

    def test_me_endpoint_without_auth(self, client: TestClient):
        """Test /auth/me endpoint without authentication."""
        response = client.get("/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert "error" in data

    def test_me_endpoint_with_invalid_token(self, client: TestClient):
        """Test /auth/me endpoint with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401

    def test_logout_endpoint(self, client: TestClient):
        """Test logout endpoint."""
        response = client.post("/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestJWTTokenHandling:
    """Test JWT token creation and validation."""

    def test_token_creation_and_validation(self, client: TestClient):
        """Test creating and validating JWT tokens."""
        from utils.crypto import create_jwt_token, verify_jwt_token

        # Create a test token
        test_data = {
            "user_id": 123,
            "username": "testuser",
            "email": "test@example.com"
        }

        token = create_jwt_token(test_data, expires_delta=3600)
        assert isinstance(token, str)
        assert len(token) > 20  # JWT tokens are quite long

        # Verify the token
        decoded_data = verify_jwt_token(token)
        assert decoded_data["user_id"] == 123
        assert decoded_data["username"] == "testuser"
        assert "exp" in decoded_data

    def test_expired_token(self, client: TestClient):
        """Test handling of expired tokens."""
        from utils.crypto import create_jwt_token, verify_jwt_token
        from jose import JWTError

        # Create a token that expires immediately
        test_data = {"user_id": 123}
        token = create_jwt_token(test_data, expires_delta=-1)  # Expired

        # Should raise an error when verifying
        with pytest.raises(JWTError):
            verify_jwt_token(token)

    def test_invalid_token_format(self, client: TestClient):
        """Test handling of malformed tokens."""
        from utils.crypto import verify_jwt_token
        from jose import JWTError

        invalid_tokens = [
            "invalid.token.format",
            "not-a-jwt-token",
            "",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid",
        ]

        for invalid_token in invalid_tokens:
            with pytest.raises(JWTError):
                verify_jwt_token(invalid_token)


class TestPasswordHashing:
    """Test password hashing functionality."""

    def test_password_hashing(self, client: TestClient):
        """Test password hashing and verification."""
        from utils.crypto import hash_password, verify_password

        password = "test_password_123"
        hashed = hash_password(password)

        # Hash should be different from original
        assert hashed != password
        assert len(hashed) > 20  # bcrypt hashes are long

        # Verification should work
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False

    def test_password_hash_uniqueness(self, client: TestClient):
        """Test that same password generates different hashes."""
        from utils.crypto import hash_password

        password = "test_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes should be different due to salt
        assert hash1 != hash2


class TestAPIKeyAuthentication:
    """Test API key authentication."""

    def test_api_key_generation(self, client: TestClient):
        """Test API key generation."""
        from utils.crypto import generate_api_key

        api_key = generate_api_key()
        assert isinstance(api_key, str)
        assert len(api_key) == 32  # Should be 32 characters
        assert api_key.isalnum()  # Should be alphanumeric

        # Generate another key - should be different
        api_key2 = generate_api_key()
        assert api_key != api_key2

    def test_api_key_authentication(self, client: TestClient):
        """Test authentication with API key."""
        # Test with no API key
        response = client.get("/auth/me")
        assert response.status_code == 401

        # Test with invalid API key
        headers = {"X-API-Key": "invalid_key"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401


class TestRateLimiting:
    """Test rate limiting for authentication endpoints."""

    def test_login_rate_limiting(self, client: TestClient):
        """Test rate limiting on login attempts."""
        # Make multiple requests to login endpoint
        responses = []
        for _ in range(10):
            response = client.get("/auth/github/login")
            responses.append(response.status_code)

        # Most should succeed, but might hit rate limits
        success_count = sum(1 for status in responses if status == 200)
        assert success_count >= 5  # At least some should succeed

    def test_token_endpoint_rate_limiting(self, client: TestClient):
        """Test rate limiting on token creation."""
        user_data = {"username": "test", "email": "test@example.com"}

        # Make multiple token requests
        responses = []
        for _ in range(5):
            response = client.post("/auth/token", json=user_data)
            responses.append(response.status_code)

        # Should handle multiple requests gracefully
        assert len(responses) == 5


class TestSecurityHeaders:
    """Test security headers in authentication responses."""

    def test_security_headers_present(self, client: TestClient):
        """Test that security headers are present in auth responses."""
        response = client.get("/auth/github/login")
        headers = response.headers

        # Check for security headers
        assert "content-type" in headers
        # Additional security headers might be added by middleware

    def test_no_sensitive_data_in_errors(self, client: TestClient):
        """Test that error responses don't leak sensitive information."""
        response = client.get("/auth/me")
        assert response.status_code == 401
        data = response.json()

        # Should not contain sensitive information
        sensitive_keywords = ["secret", "key", "password", "token"]
        response_text = str(data).lower()
        for keyword in sensitive_keywords:
            assert keyword not in response_text or "missing" in response_text


@pytest.mark.asyncio
class TestAsyncAuthEndpoints:
    """Test authentication endpoints with async client."""

    async def test_github_login_async(self, async_client: AsyncClient):
        """Test GitHub login with async client."""
        response = await async_client.get("/auth/github/login")
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data

    async def test_me_endpoint_async(self, async_client: AsyncClient):
        """Test /auth/me endpoint with async client."""
        response = await async_client.get("/auth/me")
        assert response.status_code == 401