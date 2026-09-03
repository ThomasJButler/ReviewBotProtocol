"""Shared fixtures. The environment is fixed BEFORE the app is imported,
because config.settings builds the Settings object at import time, and any
cloud key or tracing variable in the developer's shell is removed first so
the local-only guard does not trip on the developer's other projects."""

import hashlib
import hmac
import os
import socket
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for _name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY", "SENTRY_DSN",
              "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY", "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2",
              "LANGSMITH_TRACING", "LANGCHAIN_TRACING"):
    os.environ.pop(_name, None)


def _rsa_pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()


_TMP = tempfile.mkdtemp(prefix="reviewbot-tests-")
TEST_WEBHOOK_SECRET = "test-webhook-secret"
TEST_LOCAL_TOKEN = "test-local-token"
TEST_PRIVATE_KEY = _rsa_pem()

_TEST_ENV = {
    "DEBUG": "false",
    "GITHUB_APP_ID": "123456",
    "GITHUB_PRIVATE_KEY": TEST_PRIVATE_KEY,
    "GITHUB_WEBHOOK_SECRET": TEST_WEBHOOK_SECRET,
    "DATABASE_URL": f"sqlite:///{_TMP}/test.db",
    "LOG_LEVEL": "WARNING",
    "LOCAL_API_TOKEN": TEST_LOCAL_TOKEN,
    "ALLOWED_HOSTS": "localhost,127.0.0.1,reviewbot.example.org",
    "OLLAMA_MODEL": "fake-model",
    "STRICT_LOCAL": "true",
    "MAX_WEBHOOK_BODY_BYTES": str(1024 * 1024),
}
for _k, _v in _TEST_ENV.items():
    os.environ[_k] = _v


def sign(payload: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def webhook_headers(payload: bytes, event: str = "pull_request", delivery: str = None) -> dict:
    return {
        "X-GitHub-Event": event,
        "X-Hub-Signature-256": sign(payload),
        "X-GitHub-Delivery": delivery or f"delivery-{uuid.uuid4()}",
        "Content-Type": "application/json",
    }


class StubQueue:
    """Records submissions instead of running reviews."""

    def __init__(self, outcome: str = "queued", raise_with: Exception = None):
        self.submissions = []
        self.depth = 0
        self.current_job = None
        self.alive = True
        self.pending_jobs = []
        self.outcome = outcome
        self.raise_with = raise_with

    async def submit(self, **kwargs) -> str:
        if self.raise_with:
            raise self.raise_with
        self.submissions.append(kwargs)
        return self.outcome


@pytest.fixture(scope="session")
def app():
    from main import app as fastapi_app
    return fastapi_app


@pytest.fixture
def fresh_db_url(tmp_path, monkeypatch):
    """A database file per test, so tests cannot see each other's rows."""
    from config.settings import settings
    url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return url


@pytest.fixture
def client(app, fresh_db_url):
    """Sync client with the lifespan running (real DB, real queue replaced by a stub)."""
    from fastapi.testclient import TestClient
    with TestClient(app, base_url="http://localhost") as c:
        app.state.queue = StubQueue()
        yield c


@pytest.fixture
def stub_queue(app, client):
    return app.state.queue


@pytest.fixture
async def db(fresh_db_url):
    """Fresh engine and database bound to the current test's event loop."""
    from database.connection import close_db, init_db
    factory = await init_db(fresh_db_url)
    yield factory
    await close_db()


@pytest.fixture
def pr_payload() -> dict:
    user = {"id": 7, "login": "octocat"}
    repo = {"id": 1, "full_name": "octocat/repo", "private": False, "fork": False}
    return {
        "action": "opened",
        "number": 42,
        "pull_request": {
            "number": 42, "title": "Add feature", "draft": False, "state": "open",
            "head": {"ref": "feature", "sha": "a" * 40, "repo": repo},
            "base": {"ref": "main", "sha": "b" * 40, "repo": repo},
            "user": user,
        },
        "repository": repo,
        "installation": {"id": 555},
        "sender": user,
    }


class EgressBlocked(RuntimeError):
    pass


@pytest.fixture
def no_egress(monkeypatch):
    """Socket-level guard: only loopback may be dialled. Sits below every HTTP stack."""
    allowed = {"127.0.0.1", "localhost", "::1"}
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def guarded_getaddrinfo(host, *args, **kwargs):
        if str(host) not in allowed:
            raise EgressBlocked(f"DNS lookup for {host!r} blocked by the egress guard")
        return real_getaddrinfo(host, *args, **kwargs)

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in allowed:
            raise EgressBlocked(f"connect to {host!r} blocked by the egress guard")
        return real_connect(self, address)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    return allowed


DIFF = ("@@ -1,3 +1,4 @@\n"
        " import os\n"
        "+SENTINEL_9f3a = eval(user_input)\n"
        "+password = 'hunter2hunter2'\n"
        " def main():\n")
