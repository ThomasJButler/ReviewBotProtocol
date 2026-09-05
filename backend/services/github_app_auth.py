"""GitHub App authentication without PyGithub.

An App JWT (RS256, five minutes) is exchanged for an installation access
token, which is what every API call uses. The token is scoped at minting
time to the one repository under review and the two permissions a review
needs, so even an App installed with broader rights hands this process a
token that cannot reach anything else. The token is cached until five
minutes before it expires and is never logged."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
import jwt

from config.logging import get_logger
from utils.private_key import key_file_warnings, validate_private_key  # noqa: F401  (re-exported)

logger = get_logger(__name__)
API_VERSION = "2022-11-28"
REVIEW_PERMISSIONS: Dict[str, str] = {"pull_requests": "write", "metadata": "read"}
JWT_LIFETIME_SECONDS = 300  # GitHub allows up to ten minutes; five is plenty for one token exchange


class InstallationTokenProvider:
    def __init__(self, app_id: str, private_key_pem: str, installation_id: int,
                 base_url: str = "https://api.github.com", http: Optional[httpx.AsyncClient] = None,
                 repository: Optional[str] = None, permissions: Optional[Dict[str, str]] = None):
        """`repository` is the bare repository name (not owner/name); when given,
        the minted token is confined to it and to `permissions` (default: the two
        a review needs)."""
        self.app_id = str(app_id)
        self.private_key_pem = private_key_pem
        self.installation_id = int(installation_id)
        self.base_url = base_url.rstrip("/")
        self._http = http
        self.repository = repository.split("/")[-1] if repository else None
        self.permissions = dict(permissions) if permissions is not None else (dict(REVIEW_PERMISSIONS) if repository else None)
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        self._lock = asyncio.Lock()

    def app_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + JWT_LIFETIME_SECONDS, "iss": self.app_id}
        return jwt.encode(payload, self.private_key_pem, algorithm="RS256")

    def _fresh(self) -> bool:
        return bool(self._token and self._expires_at and
                    datetime.now(timezone.utc) < self._expires_at - timedelta(minutes=5))

    async def token(self) -> str:
        if self._fresh():
            return self._token  # type: ignore[return-value]
        async with self._lock:
            if self._fresh():
                return self._token  # type: ignore[return-value]
            url = f"{self.base_url}/app/installations/{self.installation_id}/access_tokens"
            headers = {
                "Authorization": f"Bearer {self.app_jwt()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "ReviewBot-Protocol",
            }
            body: Dict[str, Any] = {}
            if self.repository:
                body["repositories"] = [self.repository]
            if self.permissions:
                body["permissions"] = self.permissions
            client = self._http or httpx.AsyncClient(timeout=30.0)
            try:
                resp = await client.post(url, headers=headers, json=body) if body else await client.post(url, headers=headers)
            finally:
                if client is not self._http:
                    await client.aclose()
            if resp.status_code == 422 and body:
                raise RuntimeError("GitHub refused to scope the installation token: the App installation lacks a permission "
                                   f"a review needs ({', '.join(f'{k}:{v}' for k, v in (self.permissions or {}).items())}) "
                                   "or does not cover this repository")
            if resp.status_code != 201:
                raise RuntimeError(f"installation token request failed with HTTP {resp.status_code}")
            data = resp.json()
            granted = data.get("permissions") or {}
            if self.permissions and any(k not in self.permissions for k in granted):
                # GitHub returns exactly what was asked for; anything wider means the scoping did not apply.
                raise RuntimeError("installation token came back with wider permissions than requested; refusing to use it")
            self._token = data["token"]
            self._expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            logger.info("installation token minted", installation_id=self.installation_id,
                        expires_at=self._expires_at.isoformat())
            return self._token  # type: ignore[return-value]

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = None
