"""Shared fixtures. Environment is set BEFORE the app is imported, because
config.settings builds the Settings object at import time."""

import hashlib
import hmac
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TMP = tempfile.mkdtemp(prefix="reviewbot-tests-")
TEST_WEBHOOK_SECRET = "test-webhook-secret"

_TEST_ENV = {
    "DEBUG": "false",
    "SECRET_KEY": "test-secret-key",
    "GITHUB_APP_ID": "123456",
    "GITHUB_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----\ntest-key\n-----END RSA PRIVATE KEY-----",
    "GITHUB_WEBHOOK_SECRET": TEST_WEBHOOK_SECRET,
    "OPENAI_API_KEY": "sk-test-not-a-real-key",
    "DATABASE_URL": f"sqlite:///{_TMP}/test.db",
    "LOG_LEVEL": "WARNING",
}
for _k, _v in _TEST_ENV.items():
    os.environ.setdefault(_k, _v)


def sign(payload: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    """Produce the X-Hub-Signature-256 value GitHub would send for payload."""
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def webhook_headers(payload: bytes, event: str = "pull_request", delivery: str = "delivery-1") -> dict:
    return {
        "X-GitHub-Event": event,
        "X-Hub-Signature-256": sign(payload),
        "X-GitHub-Delivery": delivery,
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="session")
def app():
    from main import app as fastapi_app
    return fastapi_app


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient
    # Host must be on the TrustedHost allow-list (SR: hard-coded list active when DEBUG is false).
    with TestClient(app, base_url="http://localhost") as c:
        yield c


@pytest.fixture
def pr_payload() -> dict:
    """A minimal but schema-complete pull_request.opened payload."""
    user = {"id": 7, "login": "octocat", "avatar_url": "https://example.invalid/a.png"}
    repo = {
        "id": 1, "name": "repo", "full_name": "octocat/repo", "private": False,
        "html_url": "https://github.com/octocat/repo", "owner": user,
    }
    return {
        "action": "opened",
        "number": 42,
        "pull_request": {
            "id": 1001, "number": 42, "title": "Add feature", "body": "Please review",
            "state": "open", "draft": False, "merged": False,
            "html_url": "https://github.com/octocat/repo/pull/42",
            "diff_url": "https://github.com/octocat/repo/pull/42.diff",
            "patch_url": "https://github.com/octocat/repo/pull/42.patch",
            "head": {"ref": "feature", "sha": "a" * 40, "repo": repo},
            "base": {"ref": "main", "sha": "b" * 40, "repo": repo},
            "user": user,
            "created_at": "2026-09-03T10:00:00Z",
            "updated_at": "2026-09-03T10:00:00Z",
            "changed_files": 1,
        },
        "repository": repo,
        "installation": {"id": 555, "account": user},
        "sender": user,
    }


@pytest.fixture
def pr_bytes(pr_payload) -> bytes:
    return json.dumps(pr_payload).encode("utf-8")
