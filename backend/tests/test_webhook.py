"""POST /webhook/github end to end through the ASGI app, with the queue stubbed."""

import json

import pytest
import structlog

from tests.conftest import TEST_LOCAL_TOKEN, StubQueue, webhook_headers

URL = "/webhook/github"


def _body(payload: dict) -> bytes:
    return json.dumps(payload).encode()


def test_missing_headers_is_400(client):
    assert client.post(URL, content=b"{}").status_code == 400


def test_missing_event_header_is_400(client, pr_payload):
    body = _body(pr_payload)
    h = webhook_headers(body)
    del h["X-GitHub-Event"]
    assert client.post(URL, content=body, headers=h).status_code == 400


def test_missing_delivery_header_is_400(client, pr_payload):
    body = _body(pr_payload)
    h = webhook_headers(body)
    del h["X-GitHub-Delivery"]
    assert client.post(URL, content=body, headers=h).status_code == 400


def test_bad_signature_is_401_and_nothing_sensitive_is_logged(client, pr_payload):
    body = _body(pr_payload)
    h = webhook_headers(body)
    h["X-Hub-Signature-256"] = "sha256=" + "0" * 64
    with structlog.testing.capture_logs() as logs:
        r = client.post(f"{URL}?token=QUERY-SECRET-VALUE", content=body, headers=h)
    assert r.status_code == 401
    dumped = json.dumps(logs)
    assert "QUERY-SECRET-VALUE" not in dumped and "0000000000" not in dumped and "octocat/repo" not in dumped


def test_signature_over_different_body_is_401(client, pr_payload):
    body = _body(pr_payload)
    assert client.post(URL, content=body + b" ", headers=webhook_headers(body)).status_code == 401


def test_non_ascii_signature_is_401_not_500(client, pr_payload):
    body = _body(pr_payload)
    h = webhook_headers(body)
    h["X-Hub-Signature-256"] = ("sha256=é" + "0" * 63).encode("latin-1")  # bytes: the test client refuses non-ASCII text
    r = client.post(URL, content=body, headers=h)
    assert r.status_code == 401


def test_invalid_json_with_valid_signature_is_400(client):
    body = b"not json"
    assert client.post(URL, content=body, headers=webhook_headers(body)).status_code == 400


def test_ping_is_acknowledged(client):
    body = b'{"zen":"Keep it logically awesome.","hook_id":1}'
    r = client.post(URL, content=body, headers=webhook_headers(body, event="ping"))
    assert r.status_code == 200 and r.json()["status"] == "pong"


def test_other_events_are_ignored(client):
    body = b'{"ref":"refs/heads/main","commits":[]}'
    r = client.post(URL, content=body, headers=webhook_headers(body, event="push"))
    assert r.status_code == 200 and r.json()["status"] == "ignored"


def test_opened_pr_returns_202_and_queues_once(client, stub_queue, pr_payload):
    body = _body(pr_payload)
    r = client.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "queued"
    assert len(stub_queue.submissions) == 1
    s = stub_queue.submissions[0]
    assert s["repo"] == "octocat/repo" and s["pr_number"] == 42 and s["head_sha"] == "a" * 40
    assert s["installation_id"] == 555 and s["is_fork"] is False and s["fork_repo"] is None


def test_fork_pr_is_flagged(client, stub_queue, pr_payload):
    pr_payload["pull_request"]["head"]["repo"] = {"id": 2, "full_name": "Someone/Repo", "private": False, "fork": True}
    body = _body(pr_payload)
    assert client.post(URL, content=body, headers=webhook_headers(body)).status_code == 202
    s = stub_queue.submissions[0]
    assert s["is_fork"] is True and s["fork_repo"] == "Someone/Repo"


def test_deleted_fork_is_treated_as_a_fork(client, stub_queue, pr_payload):
    pr_payload["pull_request"]["head"]["repo"] = None
    body = _body(pr_payload)
    assert client.post(URL, content=body, headers=webhook_headers(body)).status_code == 202
    s = stub_queue.submissions[0]
    assert s["is_fork"] is True and s["fork_repo"] == "(deleted fork)"


def test_same_repo_with_different_case_is_not_a_fork(client, stub_queue, pr_payload):
    pr_payload["pull_request"]["head"]["repo"] = {"id": 1, "full_name": "Octocat/Repo", "private": False}
    body = _body(pr_payload)
    assert client.post(URL, content=body, headers=webhook_headers(body)).status_code == 202
    assert stub_queue.submissions[0]["is_fork"] is False


def test_malformed_repository_name_is_rejected(client, stub_queue, pr_payload):
    pr_payload["repository"]["full_name"] = "octocat/repo/../../admin?x=1"
    body = _body(pr_payload)
    assert client.post(URL, content=body, headers=webhook_headers(body)).status_code == 400
    assert stub_queue.submissions == []


@pytest.mark.parametrize("action", ["synchronize", "reopened", "ready_for_review"])
def test_trigger_actions_queue(client, stub_queue, pr_payload, action):
    pr_payload["action"] = action
    body = _body(pr_payload)
    assert client.post(URL, content=body, headers=webhook_headers(body)).status_code == 202
    assert len(stub_queue.submissions) == 1


@pytest.mark.parametrize("action", ["closed", "edited", "labeled", "converted_to_draft", "something_new"])
def test_non_trigger_actions_do_no_work(client, stub_queue, pr_payload, action):
    pr_payload["action"] = action
    body = _body(pr_payload)
    r = client.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code == 200 and r.json()["status"] == "ignored"
    assert stub_queue.submissions == []


def test_draft_pr_is_skipped(client, stub_queue, pr_payload):
    pr_payload["pull_request"]["draft"] = True
    body = _body(pr_payload)
    r = client.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code == 200 and r.json()["status"] == "skipped_draft"
    assert stub_queue.submissions == []


def test_a_pull_request_opened_by_a_bot_is_skipped_and_recorded(client, stub_queue, pr_payload):
    """Dependabot opened nine pull requests in one afternoon; each would have
    queued an hour of the machine. GitHub marks such authors type Bot."""
    pr_payload["pull_request"]["user"] = {"id": 49699333, "login": "dependabot[bot]", "type": "Bot"}
    body = _body(pr_payload)
    r = client.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code == 200 and r.json()["status"] == "skipped_bot"
    assert stub_queue.submissions == []
    d = client.get("/api/deliveries", headers={"Authorization": f"Bearer {TEST_LOCAL_TOKEN}"}).json()["items"][0]
    assert d["status"] == "skipped_bot"


def test_a_bot_pull_request_is_reviewed_when_asked(client, stub_queue, pr_payload, monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "REVIEW_BOT_PULL_REQUESTS", True)
    pr_payload["pull_request"]["user"] = {"id": 49699333, "login": "dependabot[bot]", "type": "Bot"}
    body = _body(pr_payload)
    r = client.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code == 202 and len(stub_queue.submissions) == 1


def test_signed_payload_without_installation_is_400_not_200(client, pr_payload):
    del pr_payload["installation"]
    body = _body(pr_payload)
    r = client.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code == 400
    assert "Traceback" not in r.text and "validation error" not in r.text.lower()


def test_replayed_delivery_is_rejected(client, stub_queue, pr_payload):
    body = _body(pr_payload)
    h = webhook_headers(body)
    first = client.post(URL, content=body, headers=h)
    second = client.post(URL, content=body, headers=h)
    assert first.status_code == 202
    assert second.status_code == 200 and second.json()["status"] == "duplicate"
    assert len(stub_queue.submissions) == 1


def test_queue_failure_is_503_and_the_delivery_can_be_redelivered(app, client, pr_payload):
    body = _body(pr_payload)
    h = webhook_headers(body)
    app.state.queue = StubQueue(raise_with=RuntimeError("queue exploded"))
    assert client.post(URL, content=body, headers=h).status_code == 503
    app.state.queue = StubQueue()
    assert client.post(URL, content=body, headers=h).status_code == 202, "GitHub's redelivery of a failed delivery must be accepted"
    assert len(app.state.queue.submissions) == 1


def test_shutting_down_queue_is_503(app, client, pr_payload):
    body = _body(pr_payload)
    app.state.queue = StubQueue(outcome="shutting_down")
    assert client.post(URL, content=body, headers=webhook_headers(body)).status_code == 503


def test_oversized_declared_body_is_refused_before_signature_check(client):
    body = b"x" * (2 * 1024 * 1024)
    r = client.post(URL, content=body, headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=" + "0" * 64,
                                              "X-GitHub-Delivery": "big"})
    assert r.status_code == 413


def test_oversized_chunked_body_is_refused_while_streaming(client):
    def chunks():
        for _ in range(3):
            yield b"x" * (512 * 1024)
    r = client.post(URL, content=chunks(), headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=" + "0" * 64,
                                                  "X-GitHub-Delivery": "big-chunked"})
    assert r.status_code == 413


def test_chunked_body_under_the_cap_reaches_the_signature_check(client):
    def chunks():
        yield b"{}"
    r = client.post(URL, content=chunks(), headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=" + "0" * 64,
                                                  "X-GitHub-Delivery": "small-chunked"})
    assert r.status_code == 401


def test_webhook_reachable_on_a_configured_host(app, fresh_db_url, pr_payload):
    from fastapi.testclient import TestClient
    body = _body(pr_payload)
    with TestClient(app, base_url="http://reviewbot.example.org") as c:
        app.state.queue = StubQueue()
        r = c.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code == 202, r.text


def test_unknown_host_is_rejected(app, fresh_db_url, pr_payload):
    from fastapi.testclient import TestClient
    body = _body(pr_payload)
    with TestClient(app, base_url="http://evil.example.net") as c:
        r = c.post(URL, content=body, headers=webhook_headers(body))
    assert r.status_code == 400


def test_the_pull_requests_updated_at_travels_with_the_job(client, pr_payload, stub_queue):
    """The queue answers "stale" to a delivery older than the job it holds, so a
    captured signed body replayed under a fresh id cannot cancel a newer review.
    The handler has to hand it the timestamp for that to work."""
    stamped = {**pr_payload, "pull_request": {**pr_payload["pull_request"], "updated_at": "2026-09-07T10:00:00Z"}}
    body = _body(stamped)
    assert client.post(URL, content=body, headers=webhook_headers(body)).status_code == 202
    assert stub_queue.submissions[0]["updated_at"] == "2026-09-07T10:00:00Z"
