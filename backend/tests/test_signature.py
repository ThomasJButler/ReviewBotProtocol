from tests.conftest import TEST_WEBHOOK_SECRET, sign
from utils.crypto import verify_github_signature

BODY = b'{"action":"opened","number":1}'


def test_valid_signature_with_prefix():
    assert verify_github_signature(BODY, sign(BODY)) is True


def test_valid_signature_without_prefix():
    assert verify_github_signature(BODY, sign(BODY)[len("sha256="):]) is True


def test_str_payload_matches_bytes_payload():
    assert verify_github_signature(BODY.decode("utf-8"), sign(BODY)) is True


def test_multibyte_utf8_body_verifies():
    body = '{"title":"Añadir función: 日本語 emoji 🚀"}'.encode("utf-8")
    assert verify_github_signature(body, sign(body)) is True


def test_tampered_body_rejected():
    assert verify_github_signature(BODY + b" ", sign(BODY)) is False


def test_wrong_secret_rejected():
    assert verify_github_signature(BODY, sign(BODY, secret="other")) is False


def test_empty_signature_rejected():
    assert verify_github_signature(BODY, "") is False


def test_sha1_style_value_rejected():
    assert verify_github_signature(BODY, "sha1=deadbeef") is False


def test_empty_secret_fails_closed(monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "")
    assert verify_github_signature(BODY, sign(BODY, secret=TEST_WEBHOOK_SECRET)) is False


def test_non_ascii_signature_header_returns_false():
    assert verify_github_signature(BODY, "sha256=é" + "0" * 63) is False
