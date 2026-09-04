"""The dashboard API under /api. Read-only apart from feedback. Every route
requires LOCAL_API_TOKEN; with no token configured the API is off."""

import hmac
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database.connection import db_healthy, get_db_session
from database.models import Review
from database.repositories.review_repository import ReviewRepository
from database.repositories.webhook_repository import WebhookRepository
from services.llm import ollama_health

async def require_local_token(request: Request) -> None:
    if not settings.LOCAL_API_TOKEN:
        raise HTTPException(status_code=503, detail="dashboard API disabled: set LOCAL_API_TOKEN")
    auth = request.headers.get("Authorization", "")
    presented = auth[7:] if auth.startswith("Bearer ") else request.headers.get("X-Local-Token", "")
    try:
        ok = bool(presented) and hmac.compare_digest(presented.encode("utf-8", "surrogateescape"),
                                                     settings.LOCAL_API_TOKEN.encode("utf-8"))
    except (TypeError, UnicodeError):
        ok = False
    if not ok:
        raise HTTPException(status_code=401, detail="missing or invalid local token")


api_router = APIRouter(dependencies=[Depends(require_local_token)])


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """SQLite hands back naive datetimes; they were written in UTC, so say so."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _review_dict(r: Review, with_findings: bool = False) -> dict:
    d = {
        "id": r.id, "repository": r.repository, "pr_number": r.pr_number, "pr_title": r.pr_title,
        "head_sha": r.head_sha, "is_fork": r.is_fork, "status": r.status, "model": r.model,
        "files_total": r.files_total, "files_reviewed": r.files_reviewed, "files_skipped": r.files_skipped,
        "skipped": r.skipped or [], "findings_count": r.findings_count, "severity_counts": r.severity_counts or {},
        "findings_dropped": r.findings_dropped,
        "redactions": r.redactions, "prompt_tokens": r.prompt_tokens, "output_tokens": r.output_tokens,
        "duration_seconds": r.duration_seconds, "error_message": r.error_message, "comment_url": r.comment_url,
        "useful": r.useful,
        "created_at": _iso(r.created_at),
        "completed_at": _iso(r.completed_at),
    }
    if with_findings:
        d["summary"] = r.summary
        d["findings"] = [{
            "id": f.id, "path": f.path, "line": f.line, "category": f.category, "severity": f.severity,
            "title": f.title, "evidence": f.evidence, "recommendation": f.recommendation, "confidence": f.confidence,
        } for f in r.findings]
    return d


class Feedback(BaseModel):
    useful: Optional[bool]


@api_router.get("/reviews")
async def list_reviews(repository: Optional[str] = Query(None), limit: int = Query(25, ge=1, le=100),
                       offset: int = Query(0, ge=0), session: AsyncSession = Depends(get_db_session)):
    repo = ReviewRepository(session)
    items = await repo.list(repository=repository, limit=limit, offset=offset)
    return {"items": [_review_dict(r) for r in items], "total": await repo.count(repository),
            "repositories": await repo.repositories()}


@api_router.get("/reviews/{review_id}")
async def get_review(review_id: str, session: AsyncSession = Depends(get_db_session)):
    r = await ReviewRepository(session).get(review_id)
    if r is None:
        raise HTTPException(status_code=404, detail="review not found")
    return _review_dict(r, with_findings=True)


@api_router.post("/reviews/{review_id}/feedback")
async def review_feedback(review_id: str, feedback: Feedback, session: AsyncSession = Depends(get_db_session)):
    if not await ReviewRepository(session).set_useful(review_id, feedback.useful):
        raise HTTPException(status_code=404, detail="review not found")
    return {"id": review_id, "useful": feedback.useful}


@api_router.get("/deliveries")
async def list_deliveries(limit: int = Query(20, ge=1, le=100), session: AsyncSession = Depends(get_db_session)):
    rows = await WebhookRepository(session).recent(limit)
    return {"items": [{
        "delivery_id": d.delivery_id, "event": d.event, "action": d.action, "repository": d.repository,
        "pr_number": d.pr_number, "head_sha": d.head_sha, "status": d.status, "review_id": d.review_id,
        "received_at": _iso(d.received_at),
    } for d in rows]}


@api_router.get("/status")
async def status(request: Request):
    queue = getattr(request.app.state, "queue", None)
    current = queue.current_job if queue else None
    return {
        "version": settings.APP_VERSION,
        "model": settings.OLLAMA_MODEL,
        "ollama": {**(await ollama_health(settings)), "base_url": settings.OLLAMA_BASE_URL},
        "database": await db_healthy(),
        "queue": {"depth": queue.depth if queue else 0, "alive": bool(queue and queue.alive),
                  "abandoned": queue.abandoned if queue else 0,
                  "current": {"repository": current.repo, "pr_number": current.pr_number, "head_sha": current.head_sha} if current else None},
        "limits": {"max_files_per_review": settings.MAX_FILES_PER_REVIEW, "max_patch_bytes": settings.MAX_PATCH_BYTES,
                   "review_timeout_seconds": settings.REVIEW_TIMEOUT_SECONDS, "num_ctx": settings.OLLAMA_NUM_CTX},
    }
