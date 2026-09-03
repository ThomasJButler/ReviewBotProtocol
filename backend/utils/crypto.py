"""GitHub webhook signature verification."""

import hashlib
import hmac
from typing import Union

from config.logging import get_logger
from config.settings import settings

logger = get_logger(__name__)


def verify_github_signature(payload: Union[str, bytes], signature: str) -> bool:
    """HMAC-SHA256 over the raw body, constant-time compare. Never raises."""
    if not signature or not settings.GITHUB_WEBHOOK_SECRET:
        return False
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    provided = signature[7:] if signature.startswith("sha256=") else signature
    expected = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, provided)
    except TypeError:  # non-ASCII in the header
        return False
