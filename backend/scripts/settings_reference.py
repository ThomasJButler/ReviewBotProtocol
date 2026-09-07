"""docs/SETTINGS.md, generated from the Settings class: every field with its
type, its default and the docstring under it, so the reference cannot drift
from the code. Regenerate after any change to config/settings.py and commit
the result; tests/test_settings_reference.py compares the two.

usage: .venv/bin/python scripts/settings_reference.py > ../docs/SETTINGS.md

The table is read from the class, never from an instance, so nothing set in
this machine's environment or .env can reach it; the three required secrets
render as "required". config.settings builds an instance at import, so the
environment is seeded with placeholders and cleared of the names the
local-only guard refuses before the import.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_FATAL_NAMES = ("LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING", "LANGCHAIN_TRACING", "LANGCHAIN_HANDLER",
                "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
                "MISTRAL_API_KEY", "SENTRY_DSN")
_PLACEHOLDERS = {"GITHUB_APP_ID": "0", "GITHUB_PRIVATE_KEY": "", "GITHUB_WEBHOOK_SECRET": "x" * 32,
                 "OLLAMA_BASE_URL": "http://127.0.0.1:11434", "OLLAMA_MODEL": "qwen3.5:9b", "CROSS_EXAMINE_MODEL": "",
                 "STRICT_LOCAL": "true"}


def _settings_class():
    for name in _FATAL_NAMES:
        os.environ.pop(name, None)
    os.environ.update(_PLACEHOLDERS)
    from config.settings import Settings
    return Settings


def _default(field) -> str:
    if field.is_required():
        return "required"
    value = field.default
    if isinstance(value, bool):
        return f"`{'true' if value else 'false'}`"
    if isinstance(value, str):
        return f"`{value}`" if value else "empty"
    return f"`{value}`"


def _type(field) -> str:
    return getattr(field.annotation, "__name__", str(field.annotation))


def render() -> str:
    cls = _settings_class()
    lines = [
        "# Settings reference",
        "",
        "Generated from `backend/config/settings.py` by `backend/scripts/settings_reference.py`; regenerate rather than edit "
        "(`cd backend && .venv/bin/python scripts/settings_reference.py > ../docs/SETTINGS.md`). Every setting is read from the "
        "environment or from `backend/.env`; `backend/.env.example` is the starting point. Types are what the setting is parsed "
        "to; a boolean accepts true, 1, yes or on.",
        "",
        "<!-- prettier-ignore -->",
        "| Setting | Type | Default | What it does, what it costs |",
        "| --- | --- | --- | --- |",
    ]
    for name, field in cls.model_fields.items():
        description = " ".join((field.description or "").split())
        lines.append(f"| `{name}` | {_type(field)} | {_default(field)} | {description} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.write(render())
