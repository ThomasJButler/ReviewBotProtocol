"""Cryptographic utilities for webhook signature verification."""

import hashlib
import hmac
from typing import Union

from config.settings import settings
from config.logging import get_logger

logger = get_logger(__name__)


def verify_github_signature(payload: Union[str, bytes], signature: str) -> bool:
    """
    Verify GitHub webhook signature.

    Args:
        payload: The webhook payload (raw bytes or string)
        signature: The X-Hub-Signature-256 header value

    Returns:
        bool: True if signature is valid, False otherwise
    """
    if not signature:
        logger.warning("No signature provided for webhook verification")
        return False

    if not settings.GITHUB_WEBHOOK_SECRET:
        logger.error("GitHub webhook secret not configured")
        return False

    # Convert payload to bytes if it's a string
    if isinstance(payload, str):
        payload = payload.encode('utf-8')

    # Remove 'sha256=' prefix if present
    if signature.startswith('sha256='):
        signature = signature[7:]

    # Create expected signature
    expected_signature = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(expected_signature, signature)

    if not is_valid:
        logger.warning(
            "Invalid webhook signature",
            provided_signature=signature[:10] + "..." if len(signature) > 10 else signature,
            expected_signature=expected_signature[:10] + "..."
        )

    return is_valid


def generate_api_key() -> str:
    """
    Generate a secure API key for internal authentication.

    Returns:
        str: A secure random API key
    """
    import secrets
    import string

    # Generate 32 character API key
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        str: Hashed password
    """
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        bool: True if password matches, False otherwise
    """
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)


def create_jwt_token(data: dict, expires_delta: int = 3600) -> str:
    """
    Create a JWT token.

    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time in seconds

    Returns:
        str: JWT token
    """
    from jose import jwt
    from datetime import datetime, timedelta, timezone

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(seconds=expires_delta)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def verify_jwt_token(token: str) -> dict:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token to verify

    Returns:
        dict: Decoded token data

    Raises:
        jose.JWTError: If token is invalid or expired
    """
    from jose import jwt, JWTError

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        raise


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging.

    Args:
        data: The sensitive string to mask
        visible_chars: Number of characters to leave visible at the start

    Returns:
        str: Masked string
    """
    if not data or len(data) <= visible_chars:
        return "*" * len(data) if data else ""

    return data[:visible_chars] + "*" * (len(data) - visible_chars)