"""Configuration for the ReviewBot Protocol backend.

Everything comes from environment variables or a .env file next to the
backend. There is deliberately no setting for any cloud inference provider:
the model is a local Ollama instance, and startup refuses to run if LangSmith
tracing is switched on in the environment, because that would send prompts
(and therefore code) off the machine."""

import base64
import os
from typing import List
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TRACING_VARS = ("LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING", "LANGCHAIN_TRACING")
ALWAYS_FATAL_VARS = ("LANGCHAIN_HANDLER",)
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
TRACING_KEY_VARS = ("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY")
CLOUD_KEY_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY", "SENTRY_DSN")


class LocalOnlyViolation(RuntimeError):
    """Raised at startup when the environment would let data leave the machine."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")

    APP_NAME: str = "ReviewBot Protocol"
    APP_VERSION: str = "1.1.0"
    DEBUG: bool = False

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    GITHUB_APP_ID: str
    GITHUB_PRIVATE_KEY: str
    GITHUB_WEBHOOK_SECRET: str
    GITHUB_API_BASE_URL: str = "https://api.github.com"

    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen3.5:9b"
    OLLAMA_NUM_CTX: int = 16384
    OLLAMA_NUM_PREDICT: int = 2000
    OLLAMA_TEMPERATURE: float = 0.1
    OLLAMA_KEEP_ALIVE: str = "30m"
    OLLAMA_TIMEOUT_SECONDS: int = 600

    REVIEW_TIMEOUT_SECONDS: int = 900
    REVIEW_DRAFTS: bool = False
    MAX_FILES_PER_REVIEW: int = 25
    MAX_PATCH_BYTES: int = 32_000
    MAX_WEBHOOK_BODY_BYTES: int = 2 * 1024 * 1024
    MAX_INLINE_COMMENTS: int = 25
    MIN_FINDING_CONFIDENCE: float = 0.5

    LOCAL_API_TOKEN: str = ""
    STRICT_LOCAL: bool = True

    LOG_LEVEL: str = "INFO"
    LOG_PROMPTS: bool = False

    DATABASE_URL: str = "sqlite:///./reviews.db"
    DATABASE_ECHO: bool = False

    @property
    def allowed_hosts_list(self) -> List[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @field_validator("GITHUB_PRIVATE_KEY", mode="before")
    @classmethod
    def parse_private_key(cls, v):
        """Accept PEM text, a path to a PEM file, or base64-encoded PEM."""
        if not v:
            return v
        if v.startswith("/") or v.startswith("./") or v.startswith("~"):
            path = os.path.expanduser(v)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
        if "-----BEGIN" not in v:
            try:
                decoded = base64.b64decode(v).decode("utf-8")
                if "-----BEGIN" in decoded:
                    return decoded
            except Exception:
                pass
        return v.replace("\\n", "\n")

    @field_validator("DEBUG", "REVIEW_DRAFTS", "LOG_PROMPTS", "STRICT_LOCAL", mode="before")
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @model_validator(mode="after")
    def refuse_to_leak(self):
        """The local-only guard. Tracing variables are always fatal because
        langchain-core would post every prompt to LangSmith. Cloud API keys
        are fatal only under STRICT_LOCAL (the default); nothing here reads
        them, but their presence contradicts the deployment claim."""
        for name in TRACING_VARS:
            if os.environ.get(name, "").strip().lower() == "true":
                raise LocalOnlyViolation(f"{name} is set to true; ReviewBot refuses to start with LangSmith tracing enabled")
        for name in ALWAYS_FATAL_VARS:
            if os.environ.get(name):
                raise LocalOnlyViolation(f"{name} is set; ReviewBot refuses to start with a LangChain tracing handler configured")
        if self.STRICT_LOCAL:
            host = (urlparse(self.OLLAMA_BASE_URL).hostname or "").lower()
            if host not in LOOPBACK_HOSTS:
                raise LocalOnlyViolation(
                    f"OLLAMA_BASE_URL points at {host!r}; under STRICT_LOCAL the model must be on this machine (loopback)")
            for name in TRACING_KEY_VARS + CLOUD_KEY_VARS:
                if os.environ.get(name):
                    raise LocalOnlyViolation(
                        f"{name} is present in the environment; unset it or set STRICT_LOCAL=false (nothing in ReviewBot uses it)")
        return self


settings = Settings()
