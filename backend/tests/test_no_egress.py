"""The 'fully local' proof.

Part one: the socket guard itself. Part two: no cloud SDK is installed and no
tracer is armed. Part three: the production model client is local. Part
four: a real review through the real Ollama with the guard active, run only
when REVIEWBOT_E2E=1. Only part four is an end-to-end proof of egress; the
rest pin the configuration that makes it true."""

import importlib.util
import os
import socket

import pytest

from tests.conftest import DIFF, EgressBlocked


def test_guard_blocks_a_public_host(no_egress):
    with pytest.raises(EgressBlocked):
        socket.create_connection(("1.1.1.1", 53), timeout=1)


def test_guard_allows_loopback(no_egress):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    try:
        with socket.create_connection(("127.0.0.1", srv.getsockname()[1]), timeout=1):
            pass
    finally:
        srv.close()


@pytest.mark.parametrize("module", ["openai", "langchain_openai", "anthropic", "sentry_sdk", "langchain_community"])
def test_no_cloud_sdk_is_installed(module):
    assert importlib.util.find_spec(module) is None, f"{module} must not be in the runtime environment"


def test_langsmith_tracing_is_off_after_importing_the_app(app):
    from langsmith import utils as ls_utils
    assert ls_utils.tracing_is_enabled() is False


def test_production_model_client_is_local_and_configured():
    from config.settings import settings
    from services.llm import build_chat_model
    llm = build_chat_model(settings)
    assert llm.base_url.startswith("http://127.0.0.1")
    assert llm.model == settings.OLLAMA_MODEL
    assert llm.num_ctx == settings.OLLAMA_NUM_CTX and llm.num_predict == settings.OLLAMA_NUM_PREDICT
    assert llm.reasoning is False and llm.validate_model_on_init is False
    assert llm.temperature == settings.OLLAMA_TEMPERATURE


@pytest.mark.e2e
@pytest.mark.skipif(os.environ.get("REVIEWBOT_E2E") != "1", reason="set REVIEWBOT_E2E=1 with Ollama running on 127.0.0.1")
async def test_real_model_review_completes_with_egress_blocked(no_egress):
    from config.settings import settings
    from services.ai_reviewer import FileReviewer
    from services.llm import build_chat_model, ollama_health
    local = settings.model_copy(update={"OLLAMA_MODEL": os.environ.get("REVIEWBOT_E2E_MODEL", "qwen3.5:9b")})
    health = await ollama_health(local)
    assert health["reachable"] and health["model_present"], health
    result = await FileReviewer(build_chat_model(local), local).review_file("app.py", "python", "modified", DIFF)
    assert result.parse_ok and result.error is None
    assert any(f.line == 2 for f in result.review.findings), [f.model_dump() for f in result.review.findings]
