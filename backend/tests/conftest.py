"""Test configuration and fixtures for the Git Review Assistant backend."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient
import asyncio
import os
import tempfile
from typing import AsyncGenerator, Generator

# Import the main app
from main import app
from config.settings import settings
from database.connection import init_db, get_db_session

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    with TestClient(app) as c:
        yield c

@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        temp_db_path = tmp.name

    # Override the database URL for testing
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite:///{temp_db_path}"

    yield temp_db_path

    # Cleanup
    settings.DATABASE_URL = original_db_url
    try:
        os.unlink(temp_db_path)
    except FileNotFoundError:
        pass

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set mock environment variables for testing."""
    test_env = {
        "DEBUG": "true",
        "SECRET_KEY": "test-secret-key",
        "GITHUB_APP_ID": "123456",
        "GITHUB_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----\ntest-key\n-----END RSA PRIVATE KEY-----",
        "GITHUB_WEBHOOK_SECRET": "test-webhook-secret",
        "OPENAI_API_KEY": "sk-test-key",
        "DATABASE_URL": "sqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/1"
    }

    for key, value in test_env.items():
        monkeypatch.setenv(key, value)

    return test_env

@pytest.fixture
def sample_pr_data():
    """Sample pull request data for testing."""
    return {
        "action": "opened",
        "number": 123,
        "pull_request": {
            "id": 123456789,
            "number": 123,
            "title": "Test PR",
            "body": "This is a test pull request",
            "state": "open",
            "draft": False,
            "merged": False,
            "html_url": "https://github.com/test/repo/pull/123",
            "diff_url": "https://github.com/test/repo/pull/123.diff",
            "patch_url": "https://github.com/test/repo/pull/123.patch",
            "head": {
                "ref": "feature-branch",
                "sha": "abc123def456",
                "repo": {
                    "id": 123456,
                    "name": "repo",
                    "full_name": "test/repo"
                }
            },
            "base": {
                "ref": "main",
                "sha": "def456abc123",
                "repo": {
                    "id": 123456,
                    "name": "repo",
                    "full_name": "test/repo"
                }
            },
            "user": {
                "id": 123,
                "login": "testuser",
                "avatar_url": "https://github.com/testuser.png"
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z"
        },
        "repository": {
            "id": 123456,
            "name": "repo",
            "full_name": "test/repo",
            "private": False,
            "html_url": "https://github.com/test/repo",
            "owner": {
                "id": 123,
                "login": "testuser"
            }
        },
        "installation": {
            "id": 123456789,
            "account": {
                "id": 123,
                "login": "testuser"
            }
        },
        "sender": {
            "id": 123,
            "login": "testuser"
        }
    }

@pytest.fixture
def sample_code_review():
    """Sample code for testing review functionality."""
    return {
        "language": "python",
        "code": '''
def vulnerable_function(user_input):
    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE name = '{user_input}'"
    return execute_query(query)

def inefficient_loop():
    # Performance issue - nested loops
    result = []
    for i in range(1000):
        for j in range(1000):
            result.append(i * j)
    return result
        ''',
        "filename": "test_file.py"
    }