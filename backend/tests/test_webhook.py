"""POST /webhook/github. Signature handling is the contract we keep; the
xfail tests are the Phase 4 contract (202 + queue, replay rejection, body cap)."""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import sign, webhook_headers

URL = "/webhook/github"


@pytest.mark.xfail(strict=True, reason="SR: TrustedHost allow-list is hard-coded to railway/render/heroku/localhost; must be configurable")
def test_webhook_is_reachable_on_a_configured_public_host(app, pr_bytes):
    from fastapi.testclient import TestClient
    with TestClient(app, base_url="http://reviewbot.example.org") as c:
        with patch("handlers.webhook.add_review_to_queue", new=AsyncMock(return_value={"success": True, "task_id": "t"})), \
             patch("handlers.webhook.post_initial_status_check", new=AsyncMock(return_value=True)):
            r = c.post(URL, content=pr_bytes, headers=webhook_headers(pr_bytes))
    assert r.status_code in (200, 202), r.text


def test_missing_headers_is_400(client):
    r = client.post(URL, content=b"{}")
    assert r.status_code == 400


def test_missing_event_header_is_400(client, pr_bytes):
    h = webhook_headers(pr_bytes)
    del h["X-GitHub-Event"]
    r = client.post(URL, content=pr_bytes, headers=h)
    assert r.status_code == 400


def test_bad_signature_is_401(client, pr_bytes):
    h = webhook_headers(pr_bytes)
    h["X-Hub-Signature-256"] = "sha256=" + "0" * 64
    r = client.post(URL, content=pr_bytes, headers=h)
    assert r.status_code == 401


def test_signature_over_different_body_is_401(client, pr_bytes):
    h = webhook_headers(pr_bytes)
    r = client.post(URL, content=pr_bytes + b" ", headers=h)
    assert r.status_code == 401


def test_invalid_json_with_valid_signature_is_400(client):
    body = b"not json"
    r = client.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code == 400


def test_opened_pr_is_queued_exactly_once(client, pr_bytes):
    with patch("handlers.webhook.add_review_to_queue", new=AsyncMock(return_value={"success": True, "task_id": "t"})) as q, \
         patch("handlers.webhook.post_initial_status_check", new=AsyncMock(return_value=True)):
        r = client.post(URL, content=pr_bytes, headers=webhook_headers(pr_bytes))
    assert r.status_code in (200, 202)
    assert q.await_count == 1
    kwargs = q.await_args.kwargs
    assert kwargs["review_request"].repository == "octocat/repo"
    assert kwargs["review_request"].pr_number == 42
    assert kwargs["installation_id"] == 555


def test_draft_pr_is_skipped(client, pr_payload):
    pr_payload["pull_request"]["draft"] = True
    body = json.dumps(pr_payload).encode()
    with patch("handlers.webhook.add_review_to_queue", new=AsyncMock()) as q:
        r = client.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code in (200, 202)
    assert q.await_count == 0


def test_closed_pr_does_no_work(client, pr_payload):
    pr_payload["action"] = "closed"
    body = json.dumps(pr_payload).encode()
    with patch("handlers.webhook.add_review_to_queue", new=AsyncMock()) as q:
        r = client.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code in (200, 202)
    assert q.await_count == 0


def test_signed_payload_without_installation_is_not_a_500(client, pr_payload):
    del pr_payload["installation"]
    body = json.dumps(pr_payload).encode()
    r = client.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code < 500


@pytest.mark.xfail(strict=True, reason="SR: ping and unknown events raise inside the handler and come back as 200 with the exception text")
def test_ping_event_is_acknowledged_cleanly(client):
    body = b'{"zen":"Keep it logically awesome.","hook_id":1}'
    r = client.post(URL, content=body, headers=webhook_headers(body, event="ping"))
    assert r.status_code == 200
    assert "failed" not in r.text.lower()
    assert "Traceback" not in r.text and "not a valid" not in r.text


@pytest.mark.xfail(strict=True, reason="Phase 4 step 4: webhook must return 202 immediately and hand off to the queue")
def test_opened_pr_returns_202_fast(client, pr_bytes):
    started = time.perf_counter()
    with patch("handlers.webhook.post_initial_status_check", new=AsyncMock(return_value=True)):
        r = client.post(URL, content=pr_bytes, headers=webhook_headers(pr_bytes))
    assert r.status_code == 202
    assert time.perf_counter() - started < 1.0


@pytest.mark.xfail(strict=True, reason="Phase 4 step 4: duplicate X-GitHub-Delivery must be rejected")
def test_replayed_delivery_is_rejected(client, pr_bytes):
    h = webhook_headers(pr_bytes, delivery="dup-1")
    with patch("handlers.webhook.add_review_to_queue", new=AsyncMock(return_value={"success": True, "task_id": "t"})) as q, \
         patch("handlers.webhook.post_initial_status_check", new=AsyncMock(return_value=True)):
        first = client.post(URL, content=pr_bytes, headers=h)
        second = client.post(URL, content=pr_bytes, headers=h)
    assert first.status_code in (200, 202)
    assert second.status_code in (200, 202, 409)
    assert q.await_count == 1, "the second delivery must not queue a second review"


@pytest.mark.xfail(strict=True, reason="Phase 4 step 4: oversized bodies must be refused before they are read")
def test_oversized_body_is_refused(client):
    body = b"x" * (26 * 1024 * 1024)
    r = client.post(URL, content=body, headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=" + "0" * 64})
    assert r.status_code == 413
