"""Configuration for the ReviewBot Protocol backend.

Everything comes from environment variables or a .env file next to the
backend. There is deliberately no setting for any cloud inference provider:
the model is a local Ollama instance, and startup refuses to run if LangSmith
tracing is switched on in the environment, because that would send prompts
(and therefore code) off the machine. The reference for every setting is
docs/SETTINGS.md, generated from this file."""

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
    """Every field below carries its meaning, unit, default and cost as a docstring;
    scripts/settings_reference.py renders them into docs/SETTINGS.md, and a test
    keeps the two equal."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore",
                                      use_attribute_docstrings=True)

    APP_NAME: str = "ReviewBot Protocol"
    """The name in the startup log and the API's OpenAPI title. Cosmetic."""
    APP_VERSION: str = "1.2.0"
    """The version /health and /api/status report, matching the CHANGELOG entry. Bumped with a release."""
    DEBUG: bool = False
    """Console-formatted logs instead of JSON lines, `/docs` and `/openapi.json` served, uvicorn reloading on a
    file change, and the exception's type name in the body of a 500. Off for anything GitHub can reach."""

    HOST: str = "127.0.0.1"
    """The interface uvicorn binds. Loopback by default: GitHub reaches the webhook through a tunnel or a
    reverse proxy that forwards only that path, never through this port being public."""
    PORT: int = 8000
    """The port uvicorn binds when the backend is started with `python main.py`. The dashboard's BACKEND_URL must
    name the same one; `scripts/dev-up.sh` assumes the default and passes 8000 to uvicorn and to the tunnel."""
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    """Comma-separated bare hostnames the backend answers for (the Host header check). Add the tunnel or
    proxy hostname without scheme or path; a pasted URL is reduced to its hostname. Loopback only means
    GitHub cannot reach the webhook, and startup says so."""
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    """Comma-separated origins allowed by CORS. The dashboard calls the backend server-side, so this rarely changes."""

    GITHUB_APP_ID: str
    """The App's numeric id from its settings page. Required."""
    GITHUB_PRIVATE_KEY: str
    """The App's private key: PEM text, a path to the .pem file (outside the repository at mode 600, or startup
    warns), or base64 of the PEM. Required; a key that cannot sign a JWT fails at startup, not at the first webhook."""
    GITHUB_WEBHOOK_SECRET: str
    """The secret typed into the App's webhook form; every delivery's signature is checked against it before the
    body is parsed. Required, at least 16 characters: openssl rand -hex 32."""
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    """GitHub's REST API, the one host the backend talks to besides Ollama. Changes only for GitHub Enterprise Server."""

    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    """Where Ollama listens. Under STRICT_LOCAL it must be a loopback address, which is the whole privacy claim."""
    OLLAMA_MODEL: str = "qwen3.5:9b"
    """The reviewer model's Ollama tag, the one the prompts were measured against (docs/benchmarks). A bigger model
    costs more seconds per file and more memory; measure before switching."""
    OLLAMA_NUM_CTX: int = 16384
    """The context window in tokens. MAX_PATCH_BYTES must fit inside it beside the prompt and the reply; raising it
    lets a bigger file through and costs memory per resident model, roughly in proportion."""
    OLLAMA_NUM_PREDICT: int = 2000
    """The most tokens one reply may have. The schema caps findings at twenty, so a reply rarely nears it; lower
    and a long review is cut mid-JSON and lost."""
    OLLAMA_TEMPERATURE: float = 0.1
    """Sampling temperature, the value the prompts were measured at. Higher gives more varied findings and more
    false positives."""
    OLLAMA_KEEP_ALIVE: str = "30m"
    """How long Ollama keeps the reviewer loaded after a call. Shorter frees memory sooner and reloads the model
    for the next review, about ten seconds on the reference laptop."""
    OLLAMA_TIMEOUT_SECONDS: int = 600
    """The HTTP timeout for one model call, in seconds. A rewrite-sized file on the 9B takes about two minutes; a
    call that hits this is a failed file, not a failed review."""

    REVIEW_TIMEOUT_SECONDS: int = 3600
    """The ceiling on one review, in seconds. A review that hits it posts the files that finished, lists the rest
    under Not reviewed and records how far it got. A rewrite-sized diff costs the 9B about two minutes a file,
    twice with the cross-examiner, so 25 files can need most of an hour."""
    REVIEW_SECONDS_PER_FILE: int = 300
    """The review's own budget: its file count times this, never above the ceiling, minus a 60 second margin so
    it fires first. A two-file pull request then stops holding the queue for an hour. 0 leaves only the ceiling."""
    REVIEW_DRAFTS: bool = False
    """Review draft pull requests too. Off: a draft is recorded as skipped_draft and reviewed when marked ready."""
    REVIEW_BOT_PULL_REQUESTS: bool = False
    """Review pull requests opened by a bot (dependabot, renovate). Off: they are recorded as skipped_bot; each
    would cost the machine about an hour."""
    REVIEW_RETENTION_DAYS: int = 365
    """Reviews and their findings older than this many days are deleted at startup and then nightly, never a row still
    running; 0 keeps everything. A webhook delivery that old is not deleted but stripped to a tombstone of its delivery
    id, the SHA-256 of its signed body, its event and the time it arrived, with status expired, because GitHub's
    signature never expires and that hash is the only thing that stops a captured delivery being replayed; the
    tombstones, a couple of hundred bytes each, are kept for as long as the database exists. A deleted review's
    dashboard link becomes a 404, so scripts/export_reviews.py writes what is worth keeping to JSON first."""
    MAX_FILES_PER_REVIEW: int = 25
    """The most files one review reads, riskiest first by path and size; the rest are listed under Not reviewed.
    Each file is one model call, two with the cross-examiner."""
    MAX_PATCH_BYTES: int = 32_000
    """The largest per-file diff sent to the model, in bytes. At about 2.8 bytes a token it must fit
    OLLAMA_NUM_CTX beside the prompt and the reply; a bigger file is skipped with a reason, never truncated."""
    MAX_WEBHOOK_BODY_BYTES: int = 2 * 1024 * 1024
    """The most bytes a webhook delivery may carry, checked on Content-Length and again while streaming, before
    the signature check. GitHub's pull request payloads are far smaller."""
    MAX_INLINE_COMMENTS: int = 25
    """The most findings attached as inline review comments; the rest go into the review body, since GitHub
    rejects a review with too many."""
    MIN_FINDING_CONFIDENCE: float = 0.5
    """A finding the model rates below this confidence is dropped. The measured false-positive rate assumes this
    value; lower keeps more of the model's doubts."""
    VERIFY_FINDINGS: bool = False
    """A second pass by the same model that tries to refute each finding before it is posted. Off: measured in
    docs/benchmarks, it removes some false positives at one extra call per finding."""
    MAX_VERIFY_CALLS_PER_REVIEW: int = 40
    """The verify pass stops after this many calls in one review; later findings are posted unverified."""
    CROSS_EXAMINE_MODEL: str = ""
    """The Ollama tag of a second model from a different family that judges every finding and may add its own
    (gemma4:12b was measured). Empty means off. One call per file, and with both models resident their memory together."""
    CROSS_EXAMINE_MAX_CALLS_PER_REVIEW: int = 25
    """The cross-examiner stops after this many calls in one review, one per file; later files keep the first review."""
    CROSS_EXAMINE_KEEP_ALIVE: str = "30m"
    """How long Ollama keeps the cross-examiner loaded after a call, like OLLAMA_KEEP_ALIVE."""
    CROSS_EXAMINE_SEQUENTIAL: bool = False
    """Run the two models one at a time: review every file, unload the reviewer, cross-examine every file, unload
    the cross-examiner. For a machine that cannot hold both at once (the 32 GB reference laptop); costs a reload
    between the phases."""
    CROSS_EXAMINE_NOTE_FIRST: bool = False
    """The cross-examiner writes its summary note before its verdicts. Measured both ways in docs/benchmarks;
    verdicts first (off) scored higher on the corpus."""

    LOCAL_API_TOKEN: str = ""
    """The bearer token the dashboard sends on every /api call; the same value goes in the dashboard's .env.local.
    Empty switches the dashboard API off: every /api route answers 503 and the dashboard shows nothing."""
    STRICT_LOCAL: bool = True
    """The local-only guard: refuse to start if OLLAMA_BASE_URL is not loopback, a model tag looks like an Ollama
    cloud model, or a cloud API key (OpenAI, Anthropic, Google, Mistral, Sentry, LangSmith) is in the environment.
    LangSmith tracing variables are fatal regardless. False only when your shell carries keys for other projects."""

    LOG_LEVEL: str = "INFO"
    """The logging level for the backend's JSON log lines."""
    LOG_PROMPTS: bool = False
    """Log the full prompt of every model call, diff included. Off; on only for a debugging session, since the log
    then holds the code."""

    DATABASE_URL: str = "sqlite:///./reviews.db"
    """Where reviews live, relative to the backend directory. One backend per database, enforced by a lock file
    beside it."""
    DATABASE_ECHO: bool = False
    """Log every SQL statement the backend runs. Off; on only while debugging the database layer."""

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

    @field_validator("DEBUG", "REVIEW_DRAFTS", "REVIEW_BOT_PULL_REQUESTS", "LOG_PROMPTS", "STRICT_LOCAL", "VERIFY_FINDINGS", "CROSS_EXAMINE_SEQUENTIAL",
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
