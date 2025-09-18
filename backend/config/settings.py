"""Configuration settings for the Git Review Assistant backend."""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # App Configuration
    APP_NAME: str = "Git Review Assistant API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str
    ALLOWED_ORIGINS: str = "http://localhost:3000,https://localhost:3000"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # GitHub App Configuration
    GITHUB_APP_ID: str
    GITHUB_PRIVATE_KEY: str
    GITHUB_WEBHOOK_SECRET: str
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None

    # OpenAI Configuration
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.1
    OPENAI_MAX_TOKENS: int = 4000

    # LangChain Configuration (Course Requirements)
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "git-review-assistant"
    LANGCHAIN_TRACING_V2: bool = True

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./reviews.db"
    DATABASE_ECHO: bool = False

    # Redis Configuration (for queuing and caching)
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Rate Limiting
    GITHUB_API_RATE_LIMIT: int = 5000  # per hour
    REVIEW_RATE_LIMIT: int = 100  # per hour per user

    # Security
    WEBHOOK_TIMEOUT: int = 30  # seconds
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_FILES_PER_PR: int = 100

    # Monitoring & Logging
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: Optional[str] = None
    STRUCTURED_LOGGING: bool = True

    # Review Engine Settings
    SECURITY_SCAN_ENABLED: bool = True
    PERFORMANCE_ANALYSIS_ENABLED: bool = True
    QUALITY_ANALYSIS_ENABLED: bool = True
    MAX_REVIEW_TIME: int = 300  # seconds

    @property
    def allowed_origins_list(self) -> List[str]:
        """Get ALLOWED_ORIGINS as a list."""
        if isinstance(self.ALLOWED_ORIGINS, str):
            return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
        return self.ALLOWED_ORIGINS

    @field_validator("GITHUB_PRIVATE_KEY", mode="before")
    @classmethod
    def parse_private_key(cls, v):
        """Parse GitHub private key, handling both file path and direct content."""
        if not v:
            return v

        # If it looks like a file path, read the file
        if v.startswith("/") or v.startswith("./"):
            try:
                with open(v, "r") as f:
                    return f.read()
            except FileNotFoundError:
                pass

        # Handle base64 encoded keys or direct PEM content
        if not v.startswith("-----BEGIN"):
            # Assume it's base64 encoded
            import base64
            try:
                return base64.b64decode(v).decode("utf-8")
            except Exception:
                pass

        return v

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        """Parse debug flag from string or boolean."""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.DEBUG

    @property
    def database_config(self) -> dict:
        """Get database configuration."""
        return {
            "url": self.DATABASE_URL,
            "echo": self.DATABASE_ECHO,
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }

    @property
    def redis_config(self) -> dict:
        """Get Redis configuration."""
        return {
            "url": self.REDIS_URL,
            "db": self.REDIS_DB,
            "password": self.REDIS_PASSWORD,
            "decode_responses": True,
            "retry_on_timeout": True,
        }

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }


# Global settings instance
settings = Settings()