"""GitHub App authentication without PyGithub.

An App JWT (RS256, ten minutes) is exchanged for an installation access
token, which is what every API call uses. The token is cached until five
minutes before it expires. This is the whole of what PyGithub was doing for
us, and it is the part that never worked in the previous version."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt

from config.logging import get_logger

logger = get_logger(__name__)
API_VERSION = "2022-11-28"


class InstallationTokenProvider:
    def __init__(self, app_id: str, private_key_pem: str, installation_id: int,
                 base_url: str = "https://api.github.com", http: Optional[httpx.AsyncClient] = None):
        self.app_id = str(app_id)
        self.private_key_pem = private_key_pem
        self.installation_id = int(installation_id)
        self.base_url = base_url.rstrip("/")
        self._http = http
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        self._lock = asyncio.Lock()

    def app_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 540, "iss": self.app_id}
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
            client = self._http or httpx.AsyncClient(timeout=30.0)
            try:
                resp = await client.post(url, headers=headers)
            finally:
                if client is not self._http:
                    await client.aclose()
            if resp.status_code != 201:
                raise RuntimeError(f"installation token request failed with HTTP {resp.status_code}")
            data = resp.json()
            self._token = data["token"]
            self._expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            logger.info("installation token minted", installation_id=self.installation_id,
                        expires_at=self._expires_at.isoformat())
            return self._token  # type: ignore[return-value]

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = None
