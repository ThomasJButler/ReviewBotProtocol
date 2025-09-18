"""Logging configuration for the Git Review Assistant backend."""

import logging
import structlog
import sys
from typing import Any, Dict
from pathlib import Path

from .settings import settings


def configure_logging() -> None:
    """Configure structured logging with structlog."""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            # Add log level and timestamp
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),

            # Add context
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,

            # Format for humans in dev, JSON in production
            structlog.dev.ConsoleRenderer() if settings.DEBUG
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


class SecurityLogger:
    """Security-focused logger for sensitive operations."""

    def __init__(self):
        self.logger = get_logger("security")

    def webhook_received(self, event_type: str, repo: str, user: str = None):
        """Log webhook reception."""
        self.logger.info(
            "Webhook received",
            event_type=event_type,
            repository=repo,
            user=user or "unknown"
        )

    def authentication_attempt(self, user: str, success: bool, method: str = "github"):
        """Log authentication attempts."""
        self.logger.info(
            "Authentication attempt",
            user=user,
            success=success,
            method=method
        )

    def rate_limit_exceeded(self, user: str, endpoint: str, limit: int):
        """Log rate limit violations."""
        self.logger.warning(
            "Rate limit exceeded",
            user=user,
            endpoint=endpoint,
            limit=limit
        )

    def security_scan_result(self, repo: str, pr_number: int, issues_found: int):
        """Log security scan results."""
        self.logger.info(
            "Security scan completed",
            repository=repo,
            pr_number=pr_number,
            issues_found=issues_found
        )


class ReviewLogger:
    """Logger for review operations."""

    def __init__(self):
        self.logger = get_logger("review")

    def review_started(self, repo: str, pr_number: int, files_count: int):
        """Log review start."""
        self.logger.info(
            "Review started",
            repository=repo,
            pr_number=pr_number,
            files_count=files_count
        )

    def review_completed(self, repo: str, pr_number: int,
                        duration: float, score: float, comments_posted: int):
        """Log review completion."""
        self.logger.info(
            "Review completed",
            repository=repo,
            pr_number=pr_number,
            duration_seconds=duration,
            score=score,
            comments_posted=comments_posted
        )

    def review_failed(self, repo: str, pr_number: int, error: str):
        """Log review failure."""
        self.logger.error(
            "Review failed",
            repository=repo,
            pr_number=pr_number,
            error=error
        )

    def ai_chain_executed(self, chain_name: str, duration: float,
                         input_tokens: int = None, output_tokens: int = None):
        """Log AI chain execution."""
        self.logger.info(
            "AI chain executed",
            chain_name=chain_name,
            duration_seconds=duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )


class GitHubLogger:
    """Logger for GitHub API operations."""

    def __init__(self):
        self.logger = get_logger("github")

    def api_request(self, method: str, endpoint: str, status_code: int,
                   duration: float, rate_limit_remaining: int = None):
        """Log GitHub API requests."""
        self.logger.info(
            "GitHub API request",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration_seconds=duration,
            rate_limit_remaining=rate_limit_remaining
        )

    def api_error(self, method: str, endpoint: str, status_code: int, error: str):
        """Log GitHub API errors."""
        self.logger.error(
            "GitHub API error",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            error=error
        )

    def comment_posted(self, repo: str, pr_number: int, comment_id: int, line: int = None):
        """Log comment posting."""
        self.logger.info(
            "Comment posted to PR",
            repository=repo,
            pr_number=pr_number,
            comment_id=comment_id,
            line=line
        )


# Initialize logger instances
security_logger = SecurityLogger()
review_logger = ReviewLogger()
github_logger = GitHubLogger()

# Configure logging on import
configure_logging()