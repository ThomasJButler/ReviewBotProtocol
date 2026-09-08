"""Every setting says what it is, and docs/SETTINGS.md is what the generator
prints: a docstring under a field is the only way to document one, and the
checked-in reference cannot drift from the class."""

import sys
from pathlib import Path

from config.settings import Settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import settings_reference  # noqa: E402

REFERENCE = Path(__file__).resolve().parents[2] / "docs" / "SETTINGS.md"


def test_every_setting_carries_a_description():
    """use_attribute_docstrings reads the source with inspect, so a class with
    no source, or a field whose docstring went missing, yields None here."""
    missing = [name for name, f in Settings.model_fields.items() if not (f.description or "").strip()]
    assert missing == []
    short = [name for name, f in Settings.model_fields.items() if len(f.description) < 30]
    assert short == [], "a description shorter than a sentence is a label, not a description"


def test_the_checked_in_reference_is_what_the_generator_prints():
    rendered = settings_reference.render()
    assert "| `REVIEW_TIMEOUT_SECONDS` | int | `3600` |" in rendered
    assert "| `GITHUB_PRIVATE_KEY` | str | required |" in rendered, "a secret renders as required, never as a value"
    assert REFERENCE.read_text(encoding="utf-8") == rendered, (
        "docs/SETTINGS.md is stale: cd backend && .venv/bin/python scripts/settings_reference.py > ../docs/SETTINGS.md")
