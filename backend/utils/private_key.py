"""Checks on the GitHub App private key that must not import settings or
logging, because settings runs them while it is being built."""

import os
import stat
from typing import List

from cryptography.hazmat.primitives import serialization


def validate_private_key(pem: str) -> None:
    """Fail fast on a key that is not an RSA private key. Raises ValueError
    with a message that never includes key material."""
    try:
        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    except (ValueError, TypeError) as e:
        raise ValueError(f"GITHUB_PRIVATE_KEY is not a readable unencrypted PEM private key ({type(e).__name__})") from None
    if not hasattr(key, "sign") or getattr(key, "key_size", 0) < 2048:
        raise ValueError("GITHUB_PRIVATE_KEY must be an RSA private key of at least 2048 bits")


def key_file_warnings(path: str) -> List[str]:
    """Advice about a private key file that is readable by others."""
    warnings: List[str] = []
    try:
        st = os.stat(path)
    except OSError:
        return warnings
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        warnings.append(f"the private key file {path} is readable by other users; run: chmod 600 {path}")
    if hasattr(os, "geteuid") and st.st_uid != os.geteuid():
        warnings.append(f"the private key file {path} is owned by another user")
    return warnings
