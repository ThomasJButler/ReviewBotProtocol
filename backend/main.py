"""ReviewBot Protocol backend. Two public routes (the webhook, and a health check that says only status and version), a token-gated
dashboard API, a single-worker review queue, and a local model."""

import fcntl
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from config.logging import get_logger
from config.settings import SETTINGS_WARNINGS, settings
from database.connection import close_db, init_db
from database.repositories.review_repository import ReviewRepository
from database.repositories.webhook_repository import WebhookRepository
from handlers.review import api_router
from handlers.webhook import webhook_router
from services.llm import build_chat_model, build_cross_model
from services.review_queue import ReviewJob, ReviewQueue
from services.review_runner import RunnerDeps, run_review

logger = get_logger(__name__)


def _on_result(job: ReviewJob, ok: bool, err) -> None:
    if ok:
        logger.info("review finished", repo=job.repo, pr=job.pr_number)
    elif type(err).__name__ in ("Superseded", "SupersededError"):
        logger.info("review superseded", repo=job.repo, pr=job.pr_number, reason=str(err))
    else:
        logger.warning("review did not complete", repo=job.repo, pr=job.pr_number,
                       reason=type(err).__name__ if err else "unknown", cancel_reason=job.cancel_reason)


def _acquire_instance_lock() -> object:
    """Refuse to run two backends against one database: the second would mark
    the first's in-flight review as interrupted and run reviews concurrently."""
    from database.connection import database_path
    lock_path = Path(str(database_path() or (Path(__file__).parent / "reviews.db")) + ".lock")
    handle = open(lock_path, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError(f"another ReviewBot backend already holds {lock_path}; run one instance per database")
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting", app=settings.APP_NAME, version=settings.APP_VERSION, model=settings.OLLAMA_MODEL,
                ollama=settings.OLLAMA_BASE_URL, host=settings.HOST, port=settings.PORT)
    for advice in SETTINGS_WARNINGS:
        logger.warning("settings advice", advice=advice)
    lock = _acquire_instance_lock()
    session_factory = await init_db()
    async with session_factory() as session:
        fixed = await ReviewRepository(session).mark_interrupted()
        fixed += await WebhookRepository(session).mark_interrupted()
    if fixed:
        logger.warning("marked rows left running by a previous run as interrupted", rows=fixed)
    if set(settings.allowed_hosts_list) <= {"localhost", "127.0.0.1", "::1"}:
        logger.warning("ALLOWED_HOSTS is loopback only; add the public webhook hostname before pointing GitHub at this backend")
    deps = RunnerDeps(settings=settings, llm=build_chat_model(settings), session_factory=session_factory,
                      cross_llm=build_cross_model(settings))
    # A review cut short by the ceiling posts what it has inside the grace period: a head check,
    # one post and the row write, each bounded, about 40 s at worst (services/review_runner.py).
    queue = ReviewQueue(worker=lambda job: run_review(job, deps), timeout_seconds=settings.REVIEW_TIMEOUT_SECONDS,
                        on_result=_on_result, grace_seconds=60)
    await queue.start()
    app.state.deps = deps
    app.state.queue = queue
    try:
        yield
    finally:
        pending = queue.pending_jobs
        await queue.stop()
        if pending:
            async with session_factory() as session:
                for job in pending:
                    await WebhookRepository(session).mark(job.delivery_id, "interrupted")
            logger.warning("jobs left in the queue at shutdown; GitHub redelivery will be accepted", jobs=len(pending))
        await close_db()
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()
        except OSError:
            pass
        logger.info("stopped")


app = FastAPI(
    title=settings.APP_NAME,
    description="Local-first GitHub pull request review bot",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    logger.info("request", method=request.method, path=request.url.path, status=response.status_code)
    return response


# Middleware added later wraps everything added earlier, so the host check goes last to run first.
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins_list, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "X-Local-Token"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.error("unhandled exception", path=request.url.path, error=type(exc).__name__)
    body = {"error": "internal server error"}
    if settings.DEBUG:
        body["type"] = type(exc).__name__
    headers = {}
    origin = request.headers.get("origin")
    if origin and origin in settings.allowed_origins_list:
        headers["Access-Control-Allow-Origin"] = origin
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body, headers=headers)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


app.include_router(webhook_router, prefix="/webhook", tags=["webhook"])
app.include_router(api_router, prefix="/api", tags=["dashboard"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG, log_level=settings.LOG_LEVEL.lower())
