"""POST /webhook/github: the only public route.

Order matters: cap the body, verify the signature, parse, record the delivery
(which is the replay check, and why every signed delivery is recorded before
it is filtered), filter, enqueue, return 202. Nothing slow happens here."""

import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from config.logging import get_logger
from config.settings import settings
from database.connection import get_db_session
from database.repositories.review_repository import ReviewRepository
from database.repositories.webhook_repository import WebhookRepository
from models.github import PRAction, PRWebhookPayload, REVIEW_TRIGGERS
from utils.crypto import verify_github_signature

logger = get_logger(__name__)
webhook_router = APIRouter()


async def read_body_capped(request: Request, cap: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > cap:
        raise HTTPException(status_code=413, detail="payload too large")
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > cap:
            raise HTTPException(status_code=413, detail="payload too large")
    return bytes(buf)


def _ok(status: str, code: int = 200, **extra) -> JSONResponse:
    return JSONResponse(status_code=code, content={"status": status, **extra})


@webhook_router.post("/github", status_code=202)
async def github_webhook(request: Request, session: AsyncSession = Depends(get_db_session)):
    body = await read_body_capped(request, settings.MAX_WEBHOOK_BODY_BYTES)
    signature = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event")
    delivery_id: Optional[str] = request.headers.get("X-GitHub-Delivery")
    if not signature or not event:
        raise HTTPException(status_code=400, detail="missing X-Hub-Signature-256 or X-GitHub-Event")
    if not verify_github_signature(body, signature):
        logger.warning("webhook signature rejected", github_event=event, size=len(body))
        raise HTTPException(status_code=401, detail="invalid signature")
    if not delivery_id:
        raise HTTPException(status_code=400, detail="missing X-GitHub-Delivery")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="body is not valid JSON")

    deliveries = WebhookRepository(session)
    pr = None
    if event == "pull_request":
        try:
            pr = PRWebhookPayload.model_validate(payload)
        except ValidationError:
            raise HTTPException(status_code=400, detail="payload did not match the pull_request schema")

    # Every signed delivery is recorded, so the Status page shows pings and
    # ignored events too, and so a replay of any of them is caught.
    recorded = await deliveries.record(
        delivery_id, event, pr.action if pr else (payload.get("action") if isinstance(payload, dict) else None),
        pr.repository.full_name if pr else None, pr.number if pr else None, pr.pull_request.head.sha if pr else None,
        body_sha256=hashlib.sha256(body).hexdigest())
    if not recorded:
        logger.warning("duplicate delivery ignored", delivery_id=delivery_id, github_event=event)
        return _ok("duplicate", delivery_id=delivery_id)

    if event == "ping":
        await deliveries.mark(delivery_id, "pong")
        return _ok("pong")
    if pr is None:
        await deliveries.mark(delivery_id, "ignored")
        return _ok("ignored", github_event=event)

    try:
        action = PRAction(pr.action)
    except ValueError:
        action = None
    if action not in REVIEW_TRIGGERS:
        await deliveries.mark(delivery_id, "ignored")
        return _ok("ignored", action=pr.action)
    if pr.pull_request.draft and not settings.REVIEW_DRAFTS:
        await deliveries.mark(delivery_id, "skipped_draft")
        return _ok("skipped_draft", pr_number=pr.number)

    head_sha = pr.pull_request.head.sha
    # A head that was already reviewed to completion is never queued again, so a
    # replayed old delivery cannot cancel the review of a newer push.
    if await ReviewRepository(session).completed_for(pr.repository.full_name, pr.number, head_sha):
        await deliveries.mark(delivery_id, "duplicate")
        return _ok("duplicate", delivery_id=delivery_id, reason="head already reviewed")

    queue = request.app.state.queue
    try:
        outcome = await queue.submit(repo=pr.repository.full_name, pr_number=pr.number, head_sha=head_sha,
                                     installation_id=pr.installation.id, delivery_id=delivery_id,
                                     is_fork=pr.is_fork, fork_repo=pr.fork_repo,
                                     updated_at=pr.pull_request.updated_at or "")
    except Exception as e:
        logger.error("queue submit failed", error=type(e).__name__, delivery_id=delivery_id)
        await deliveries.mark(delivery_id, "failed")
        raise HTTPException(status_code=503, detail="review queue unavailable; GitHub may redeliver")
    if outcome in ("shutting_down", "queue_dead"):
        await deliveries.mark(delivery_id, "interrupted")
        raise HTTPException(status_code=503, detail="review queue unavailable; GitHub may redeliver")
    await deliveries.mark(delivery_id, "duplicate" if outcome in ("duplicate", "stale") else "queued")
    logger.info("webhook accepted", repo=pr.repository.full_name, pr=pr.number, action=pr.action,
                head=head_sha[:12], fork=pr.is_fork, outcome=outcome, delivery_id=delivery_id)
    return _ok("queued", 202, outcome=outcome, repository=pr.repository.full_name, pr_number=pr.number, head_sha=head_sha)
