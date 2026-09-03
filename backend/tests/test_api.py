"""The dashboard API: token gate, listing, detail, feedback, status, deliveries."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport

from database.repositories.review_repository import ReviewRepository
from database.repositories.webhook_repository import WebhookRepository
from tests.conftest import TEST_LOCAL_TOKEN, StubQueue

AUTH = {"Authorization": f"Bearer {TEST_LOCAL_TOKEN}"}


@pytest.fixture
async def api(app, db):
    app.state.queue = StubQueue()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        yield c


async def test_every_api_route_requires_the_token(api, app):
    """Every route under /api must answer 401 with no credentials. The OpenAPI
    schema is the flattened view of every route, whatever FastAPI nests."""
    checked = 0
    paths = app.openapi()["paths"]
    assert any(p.startswith("/api") for p in paths), list(paths)
    for path, operations in paths.items():
        if not path.startswith("/api"):
            continue
        concrete = path.replace("{review_id}", "x")
        for method in operations:
            r = await api.request(method.upper(), concrete, json={"useful": True} if method == "post" else None)
            assert r.status_code == 401, (method, concrete, r.status_code)
            checked += 1
    assert checked >= 5
    assert "/health" in paths and "/webhook/github" in paths


@pytest.mark.parametrize("headers", [{"Authorization": "Bearer wrong"}, {"X-Local-Token": "wrong"},
                                     {b"Authorization": b"Bearer t\xe9st"}])
async def test_wrong_tokens_are_401_not_500(api, headers):
    assert (await api.get("/api/reviews", headers=headers)).status_code == 401


async def test_api_is_disabled_without_a_configured_token(api, monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "LOCAL_API_TOKEN", "")
    assert (await api.get("/api/reviews", headers=AUTH)).status_code == 503


async def test_list_detail_and_feedback(api, db):
    async with db() as session:
        repo = ReviewRepository(session)
        r = await repo.create({"repository": "octocat/repo", "pr_number": 7, "status": "completed", "model": "m", "findings_count": 1,
                               "severity_counts": {"high": 1}})
        await repo.add_findings(r.id, [{"path": "a.py", "line": 3, "category": "security", "severity": "high",
                                        "title": "t", "evidence": "e", "recommendation": "r", "confidence": 0.9}])
    listing = (await api.get("/api/reviews", headers=AUTH)).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == r.id and listing["repositories"] == ["octocat/repo"]
    assert listing["items"][0]["severity_counts"] == {"high": 1}
    detail = (await api.get(f"/api/reviews/{r.id}", headers=AUTH)).json()
    assert detail["findings"][0]["line"] == 3 and detail["useful"] is None
    assert (await api.post(f"/api/reviews/{r.id}/feedback", headers=AUTH, json={"useful": True})).status_code == 200
    assert (await api.get(f"/api/reviews/{r.id}", headers=AUTH)).json()["useful"] is True
    assert (await api.get("/api/reviews/nope", headers=AUTH)).status_code == 404
    assert (await api.post("/api/reviews/nope/feedback", headers=AUTH, json={"useful": False})).status_code == 404


async def test_deliveries_listing(api, db):
    async with db() as session:
        w = WebhookRepository(session)
        await w.record("d-9", "pull_request", "opened", "octocat/repo", 9, "a" * 40)
        await w.mark("d-9", "completed", "rev-1")
    items = (await api.get("/api/deliveries", headers=AUTH)).json()["items"]
    assert items[0]["delivery_id"] == "d-9" and items[0]["status"] == "completed" and items[0]["review_id"] == "rev-1"
    assert set(items[0]) >= {"event", "action", "repository", "pr_number", "head_sha", "received_at"}


async def test_status_reports_ollama_queue_and_limits(api):
    with patch("handlers.review.ollama_health", new=AsyncMock(return_value={"reachable": False, "model": "fake-model", "model_present": False, "loaded": []})):
        s = (await api.get("/api/status", headers=AUTH)).json()
    assert s["model"] == "fake-model" and s["ollama"]["reachable"] is False
    assert s["queue"]["depth"] == 0 and s["queue"]["alive"] is True
    assert s["limits"]["max_files_per_review"] > 0 and s["database"] is True


async def test_health_is_public_and_minimal(api):
    r = await api.get("/health")
    assert r.status_code == 200 and set(r.json()) == {"status", "version"}


async def test_docs_and_openapi_are_off_outside_debug(api):
    assert (await api.get("/openapi.json")).status_code == 404
    assert (await api.get("/docs")).status_code == 404


def test_unhandled_errors_are_a_generic_500(app, fresh_db_url):
    from fastapi.testclient import TestClient
    with patch("handlers.review.ollama_health", new=AsyncMock(side_effect=RuntimeError("secret sk-proj-" + "x" * 40))):
        with TestClient(app, base_url="http://localhost", raise_server_exceptions=False) as c:
            r = c.get("/api/status", headers=AUTH)
    assert r.status_code == 500 and r.json() == {"error": "internal server error"}
    assert "sk-proj" not in r.text and "Traceback" not in r.text
