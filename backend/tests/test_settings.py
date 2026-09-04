"""The local-only guard and the defaults that matter."""

import pytest

from config.settings import CLOUD_KEY_VARS, LocalOnlyViolation, Settings, TRACING_KEY_VARS, TRACING_VARS

_OVERRIDDEN = ("VERIFY_FINDINGS", "DEBUG", "STRICT_LOCAL", "ALLOWED_HOSTS", "MAX_WEBHOOK_BODY_BYTES", "LOG_LEVEL", "LOCAL_API_TOKEN",
               "OLLAMA_MODEL", "DATABASE_URL", "LOG_PROMPTS", "REVIEW_DRAFTS")


def _mk(monkeypatch, clear_overrides=False, **env):
    if clear_overrides:
        for name in _OVERRIDDEN:
            monkeypatch.delenv(name, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)


def test_defaults_are_safe_with_a_clean_environment(monkeypatch):
    s = _mk(monkeypatch, clear_overrides=True)
    assert s.DEBUG is False and s.STRICT_LOCAL is True and s.LOG_PROMPTS is False and s.REVIEW_DRAFTS is False
    assert s.HOST == "127.0.0.1" and s.allowed_hosts_list == ["localhost", "127.0.0.1"]
    assert s.MAX_WEBHOOK_BODY_BYTES == 2 * 1024 * 1024 and s.LOCAL_API_TOKEN == ""
    assert s.OLLAMA_BASE_URL == "http://127.0.0.1:11434"


def test_boots_with_no_cloud_variables(monkeypatch):
    assert _mk(monkeypatch).OLLAMA_BASE_URL.startswith("http://127.0.0.1")


@pytest.mark.parametrize("var", TRACING_VARS)
def test_refuses_langsmith_tracing(monkeypatch, var):
    with pytest.raises(LocalOnlyViolation) as e:
        _mk(monkeypatch, **{var: "true"})
    assert var in str(e.value)


def test_refuses_a_langchain_handler(monkeypatch):
    with pytest.raises(LocalOnlyViolation):
        _mk(monkeypatch, LANGCHAIN_HANDLER="langchain")


def test_tracing_variable_set_to_false_is_fine(monkeypatch):
    assert _mk(monkeypatch, LANGCHAIN_TRACING_V2="false")


@pytest.mark.parametrize("var", CLOUD_KEY_VARS + TRACING_KEY_VARS)
def test_refuses_cloud_keys_under_strict_local(monkeypatch, var):
    with pytest.raises(LocalOnlyViolation) as e:
        _mk(monkeypatch, **{var: "x"})
    assert var in str(e.value)


def test_cloud_key_tolerated_when_strict_local_off(monkeypatch):
    assert _mk(monkeypatch, OPENAI_API_KEY="x", STRICT_LOCAL="false")


@pytest.mark.parametrize("url", ["http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"])
def test_loopback_ollama_accepted(monkeypatch, url):
    assert _mk(monkeypatch, OLLAMA_BASE_URL=url).OLLAMA_BASE_URL == url


def test_remote_ollama_refused_under_strict_local(monkeypatch):
    with pytest.raises(LocalOnlyViolation) as e:
        _mk(monkeypatch, OLLAMA_BASE_URL="http://gpu-box.lan:11434")
    assert "gpu-box.lan" in str(e.value)
    assert _mk(monkeypatch, OLLAMA_BASE_URL="http://gpu-box.lan:11434", STRICT_LOCAL="false")


def test_private_key_escaped_newlines_are_unescaped(monkeypatch):
    s = _mk(monkeypatch, GITHUB_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----")
    assert "\n" in s.GITHUB_PRIVATE_KEY and "\\n" not in s.GITHUB_PRIVATE_KEY


def test_verify_findings_is_off_by_default_and_parses_like_the_other_booleans():
    s = Settings(_env_file=None)
    assert s.VERIFY_FINDINGS is False and s.MAX_VERIFY_CALLS_PER_REVIEW == 40
    for raw, want in (("true", True), ("TRUE", True), ("1", True), ("on", True), ("false", False), ("0", False)):
        assert Settings(_env_file=None, VERIFY_FINDINGS=raw).VERIFY_FINDINGS is want, raw
