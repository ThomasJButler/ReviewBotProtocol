"""Main FastAPI application for Git Review Assistant backend."""

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import uvicorn
import sentry_sdk
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration

from config.settings import settings
from config.logging import get_logger, configure_logging
from handlers.webhook import webhook_router
from handlers.review import review_router
from handlers.auth import auth_router
from handlers.github import github_router
from database.connection import init_db, close_db

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Initialize Sentry if DSN is provided
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1 if settings.is_production else 1.0,
        environment="production" if settings.is_production else "development",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Git Review Assistant API", version=settings.APP_VERSION)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down Git Review Assistant API")
    await close_db()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered code review system with GitHub integration",
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Security middleware
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.railway.app", "*.render.com", "*.herokuapp.com", "localhost"]
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# Custom middleware for logging and metrics
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing."""
    start_time = time.time()

    # Get client info
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")

    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        client_ip=client_ip,
        user_agent=user_agent
    )

    try:
        response = await call_next(request)
        process_time = time.time() - start_time

        logger.info(
            "Request completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=process_time,
            client_ip=client_ip
        )

        response.headers["X-Process-Time"] = str(process_time)
        return response

    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            "Request failed",
            method=request.method,
            url=str(request.url),
            error=str(e),
            process_time=process_time,
            client_ip=client_ip
        )
        raise


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(
        "Unhandled exception",
        url=str(request.url),
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__
    )

    if settings.DEBUG:
        # In debug mode, show the actual error
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "detail": str(exc),
                "type": type(exc).__name__
            }
        )
    else:
        # In production, hide internal details
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error"}
        )


# Health check endpoints
@app.get("/health", tags=["health"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": time.time()
    }


@app.get("/health/detailed", tags=["health"])
async def detailed_health_check():
    """Detailed health check with dependency status."""
    from database.connection import get_db_health
    from services.github_client import get_github_health
    from services.ai_reviewer import get_ai_health

    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": time.time(),
        "checks": {}
    }

    # Check database
    try:
        db_health = await get_db_health()
        health_status["checks"]["database"] = {
            "status": "healthy" if db_health else "unhealthy",
            "details": db_health
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check GitHub API
    try:
        github_health = await get_github_health()
        health_status["checks"]["github"] = {
            "status": "healthy" if github_health["accessible"] else "unhealthy",
            "details": github_health
        }
    except Exception as e:
        health_status["checks"]["github"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check AI service
    try:
        ai_health = await get_ai_health()
        health_status["checks"]["ai"] = {
            "status": "healthy" if ai_health["available"] else "unhealthy",
            "details": ai_health
        }
    except Exception as e:
        health_status["checks"]["ai"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Overall status
    unhealthy_checks = [
        check for check in health_status["checks"].values()
        if check["status"] == "unhealthy"
    ]

    if unhealthy_checks:
        health_status["status"] = "degraded" if len(unhealthy_checks) < len(health_status["checks"]) else "unhealthy"

    return health_status


@app.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """Basic metrics endpoint."""
    # TODO: Implement proper metrics collection
    return {
        "requests_total": 0,
        "requests_failed": 0,
        "reviews_completed": 0,
        "avg_response_time": 0.0
    }


# Include API routers
app.include_router(
    webhook_router,
    prefix="/webhook",
    tags=["webhook"]
)

app.include_router(
    review_router,
    prefix="/review",
    tags=["review"]
)

app.include_router(
    auth_router,
    prefix="/auth",
    tags=["authentication"]
)

app.include_router(
    github_router,
    prefix="/github",
    tags=["github"]
)


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "AI-powered code review system with GitHub integration",
        "docs_url": "/docs" if settings.DEBUG else None,
        "health_url": "/health"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS if settings.is_production else 1,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
    )