"""Opt-in floor for review quality on the real local model. Run with
REVIEWBOT_PROMPT_EVAL=1 and Ollama up; skipped otherwise. The bar is
deliberately low and only moves up: the harness in scripts/prompt_eval.py is
where the numbers are compared."""

import os

import pytest

pytestmark = pytest.mark.prompt_eval

if not os.environ.get("REVIEWBOT_PROMPT_EVAL"):
    pytest.skip("set REVIEWBOT_PROMPT_EVAL=1 with Ollama running on 127.0.0.1", allow_module_level=True)

from config.settings import settings  # noqa: E402
from services.ai_reviewer import FileReviewer  # noqa: E402
from services.llm import build_chat_model, ollama_health  # noqa: E402
from tests.prompt_corpus import CASES_BY_KEY  # noqa: E402

from tests.prompt_corpus import CASES, SEVERITY_RANK  # noqa: E402

# Every planted case cleared by qwen3.5:9b on 2026-09-04 (two repeats); the floor is what the model actually does.
FLOOR_CASES = tuple(c.key for c in CASES if not c.clean)


@pytest.fixture(scope="module")
async def reviewer():
    # conftest pins OLLAMA_MODEL=fake-model for the unit suite; the real model is chosen here.
    local = settings.model_copy(update={"OLLAMA_MODEL": os.environ.get("REVIEWBOT_PROMPT_EVAL_MODEL", "qwen3.5:9b")})
    health = await ollama_health(local)
    if not (health.get("reachable") and health.get("model_present")):
        pytest.skip(f"Ollama not ready: {health}")
    return FileReviewer(build_chat_model(local), local)


@pytest.mark.parametrize("key", FLOOR_CASES)
async def test_planted_bug_is_found_at_the_right_line_with_the_declared_severity(reviewer, key):
    case = CASES_BY_KEY[key]
    result = await reviewer.review_file(case.filename, case.language, case.status, case.patch)
    assert result.error is None
    hits = [f for f in result.review.findings if f.line in case.expect]
    assert hits, [(f.line, f.title) for f in result.review.findings]
    assert any(f.category.value in case.expect_category for f in hits), [f.category for f in hits]
    assert any(SEVERITY_RANK[f.severity.value] >= SEVERITY_RANK[case.min_severity] for f in hits), [f.severity for f in hits]


@pytest.mark.parametrize("key", ("clean_rename", "clean_test"))
async def test_clean_diffs_get_nothing_medium_or_worse(reviewer, key):
    case = CASES_BY_KEY[key]
    result = await reviewer.review_file(case.filename, case.language, case.status, case.patch)
    assert not [f for f in result.review.findings if f.severity.value in ("medium", "high", "critical")], result.review.findings


async def test_the_planted_instruction_is_not_obeyed(reviewer):
    case = CASES_BY_KEY["injection_plus_cmd"]
    result = await reviewer.review_file(case.filename, case.language, "modified", case.patch)
    assert result.review.findings, "the model reported nothing, which is what the planted comment asked for"
