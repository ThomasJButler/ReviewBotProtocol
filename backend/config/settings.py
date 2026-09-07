"""Configuration for the ReviewBot Protocol backend.

Everything comes from environment variables or a .env file next to the
backend. There is deliberately no setting for any cloud inference provider:
the model is a local Ollama instance, and startup refuses to run if LangSmith
tracing is switched on in the environment, because that would send prompts
(and therefore code) off the machine."""

import base64
import os
from typing import List

SETTINGS_WARNINGS: List[str] = []  # advice gathered while loading settings; main.py logs it at startup
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

    REVIEW_TIMEOUT_SECONDS: int = 3600  # a rewrite-sized diff costs the 9B about two minutes a file, twice with the cross-examiner
    REVIEW_DRAFTS: bool = False
    MAX_FILES_PER_REVIEW: int = 25
    MAX_PATCH_BYTES: int = 32_000
    MAX_WEBHOOK_BODY_BYTES: int = 2 * 1024 * 1024
    MAX_INLINE_COMMENTS: int = 25
    MIN_FINDING_CONFIDENCE: float = 0.5
    VERIFY_FINDINGS: bool = False  # second model pass per finding that tries to refute it
    MAX_VERIFY_CALLS_PER_REVIEW: int = 40  # the verify pass stops after this many calls in one review
    CROSS_EXAMINE_MODEL: str = ""  # a second model from a different family; empty means off
    CROSS_EXAMINE_MAX_CALLS_PER_REVIEW: int = 25  # one call per file
    CROSS_EXAMINE_KEEP_ALIVE: str = "30m"
    # Run the two models one at a time: review every file, unload the reviewer, cross-examine every
    # file, unload the cross-examiner. Only for machines that cannot hold both models at once.
    CROSS_EXAMINE_SEQUENTIAL: bool = False
    # The cross-examiner writes its summary_note before its verdicts (scratchpad first, as the review
    # schema does). Measured either way by scripts/prompt_eval.py --cross-note-first; see docs/benchmarks.
    CROSS_EXAMINE_NOTE_FIRST: bool = False

    LOCAL_API_TOKEN: str = ""
    STRICT_LOCAL: bool = True

    LOG_LEVEL: str = "INFO"
    LOG_PROMPTS: bool = False

    DATABASE_URL: str = "sqlite:///./reviews.db"
    DATABASE_ECHO: bool = False

    @property
    def allowed_hosts_list(self) -> List[str]:
        # the host check compares bare hostnames, so a pasted URL ("https://x.ngrok-free.dev/webhook/github")
        # or a host:port entry is reduced to the hostname rather than silently never matching
        hosts = []
        for entry in self.ALLOWED_HOSTS.split(","):
            h = entry.strip()
            if "://" in h:
                h = h.split("://", 1)[1]
            h = h.split("/", 1)[0].split(":", 1)[0].strip().lower()
            if h:
                hosts.append(h)
        return hosts

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @field_validator("GITHUB_PRIVATE_KEY", mode="before")
    @classmethod
    def parse_private_key(cls, v):
        """Accept PEM text, a path to a PEM file, or base64-encoded PEM."""
        if not v:
            return v
        if "-----BEGIN" not in v and "\n" not in v.strip():
            # A path in any of the forms a reader might write: absolute, ~, or
            # relative (resolved against the backend directory, not the shell's cwd).
            candidate = os.path.expanduser(v.strip())
            if not os.path.isabs(candidate):
                candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), candidate)
            if os.path.isfile(candidate):
                from utils.private_key import key_file_warnings
                SETTINGS_WARNINGS.extend(key_file_warnings(candidate))
                with open(candidate, "r", encoding="utf-8") as f:
                    return f.read()
            if "/" in v or v.strip().endswith((".pem", ".key")):
                raise ValueError(f"GITHUB_PRIVATE_KEY points at {candidate}, which does not exist")
        if "-----BEGIN" not in v:
            try:
                decoded = base64.b64decode(v).decode("utf-8")
                if "-----BEGIN" in decoded:
                    return decoded
            except Exception:
                pass
        return v.replace("\\n", "\n")

    @field_validator("DEBUG", "REVIEW_DRAFTS", "LOG_PROMPTS", "STRICT_LOCAL", "VERIFY_FINDINGS", "CROSS_EXAMINE_SEQUENTIAL",
                     "CROSS_EXAMINE_NOTE_FIRST", mode="before")
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @model_validator(mode="after")
    def check_private_key_parses(self):
        """A key that cannot sign a JWT is found now, not at the first webhook."""
        if self.GITHUB_PRIVATE_KEY:
            from utils.private_key import validate_private_key
            validate_private_key(self.GITHUB_PRIVATE_KEY)
        return self

    @model_validator(mode="after")
    def check_secrets(self):
        """Catch the two ways a copied .env.example ends up with a useless secret."""
        for name in ("GITHUB_WEBHOOK_SECRET", "LOCAL_API_TOKEN"):
            value = getattr(self, name) or ""
            if name == "LOCAL_API_TOKEN" and not value:
                continue
            if value.lstrip().startswith("#") or len(value) < 16:
                raise ValueError(f"{name} must be at least 16 characters and not a comment; generate one with: openssl rand -hex 32")
        return self

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
            for name in ("OLLAMA_MODEL", "CROSS_EXAMINE_MODEL"):
                tag = (getattr(self, name) or "").lower()
                if tag.endswith("-cloud") or ":cloud" in tag:
                    raise LocalOnlyViolation(
                        f"{name} {tag!r} looks like an Ollama cloud model, which would relay prompts off this machine")
            for name in TRACING_KEY_VARS + CLOUD_KEY_VARS:
                if os.environ.get(name):
                    raise LocalOnlyViolation(
                        f"{name} is present in the environment; unset it or set STRICT_LOCAL=false (nothing in ReviewBot uses it)")
        return self


settings = Settings()
