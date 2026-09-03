"""GitHub REST client on httpx. Only the calls the review needs."""

import asyncio
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from config.logging import get_logger
from services.comment_renderer import sanitise
from services.github_app_auth import API_VERSION, InstallationTokenProvider

logger = get_logger(__name__)
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')
MAX_FILES_PAGES = 30  # GitHub caps a PR at 3000 files; 30 pages of 100
MAX_RATE_LIMIT_WAIT = 120


class GitHubError(RuntimeError):
    def __init__(self, status: int, message: str, errors: Optional[List[Any]] = None):
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status
        self.message = message
        self.errors = errors or []


class GitHubClient:
    def __init__(self, token_provider: InstallationTokenProvider, base_url: str = "https://api.github.com",
                 http: Optional[httpx.AsyncClient] = None):
        self.tokens = token_provider
        self.base_url = base_url.rstrip("/")
        self._base = urlparse(self.base_url)
        self._http = http
        self._owned = http is None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self._http

    async def aclose(self) -> None:
        if self._owned and self._http is not None:
            await self._http.aclose()
            self._http = None

    def _resolve(self, url: str) -> str:
        """Only ever send the installation token to the configured API host."""
        if not url.startswith("http"):
            return f"{self.base_url}{url}"
        parts = urlparse(url)
        if parts.scheme != self._base.scheme or parts.netloc != self._base.netloc:
            raise GitHubError(0, f"refusing to follow a link to {parts.netloc}")
        return url

    async def _request(self, method: str, url: str, *, json: Any = None, params: Optional[dict] = None,
                       _attempt: int = 0) -> httpx.Response:
        client = await self._client()
        headers = {
            "Authorization": f"token {await self.tokens.token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "ReviewBot-Protocol",
        }
        full = self._resolve(url)
        if params:  # merge into the URL: a bare params= would replace a Link URL's own query string
            full = str(httpx.URL(full).copy_merge_params(params))
        resp = await client.request(method, full, headers=headers, json=json)
        logger.info("github api", method=method, path=url if not url.startswith("http") else "(paged)",
                    status=resp.status_code, rate_remaining=resp.headers.get("x-ratelimit-remaining"))
        if resp.status_code == 401 and _attempt == 0:
            self.tokens.invalidate()
            return await self._request(method, url, json=json, params=params, _attempt=1)
        if resp.status_code in (403, 429) and _attempt < 2:
            wait = self._rate_limit_wait(resp)
            if wait is not None:
                logger.warning("github rate limited, waiting", seconds=wait)
                await asyncio.sleep(wait)
                return await self._request(method, url, json=json, params=params, _attempt=_attempt + 1)
        if not 200 <= resp.status_code < 300:
            message, errors = self._error_details(resp)
            raise GitHubError(resp.status_code, message, errors)
        return resp

    @staticmethod
    def _rate_limit_wait(resp: httpx.Response) -> Optional[int]:
        retry_after = resp.headers.get("retry-after")
        if retry_after and retry_after.isdigit():
            return min(int(retry_after), MAX_RATE_LIMIT_WAIT)
        if resp.headers.get("x-ratelimit-remaining") == "0":
            reset = resp.headers.get("x-ratelimit-reset")
            if reset and reset.isdigit():
                return max(1, min(int(reset) - int(time.time()), MAX_RATE_LIMIT_WAIT))
            return 60
        return None

    @staticmethod
    def _error_details(resp: httpx.Response) -> Tuple[str, List[Any]]:
        try:
            body = resp.json()
            return str(body.get("message", resp.text[:200])), list(body.get("errors") or [])
        except Exception:
            return resp.text[:200], []

    async def get_pull(self, repo: str, number: int) -> Dict[str, Any]:
        data = (await self._request("GET", f"/repos/{repo}/pulls/{number}")).json()
        if not isinstance(data, dict):
            raise GitHubError(0, "pull request response was not an object")
        return data

    async def list_pull_files(self, repo: str, number: int) -> Tuple[List[Dict[str, Any]], bool]:
        """All changed files, paginated. The flag says whether the page cap
        was hit and files were left unfetched."""
        files: List[Dict[str, Any]] = []
        url: Optional[str] = f"/repos/{repo}/pulls/{number}/files"
        pages = 0
        while url:
            if pages >= MAX_FILES_PAGES:
                return files, True
            resp = await self._request("GET", url, params={"per_page": 100})
            page = resp.json()
            if not isinstance(page, list):
                raise GitHubError(0, "files response was not a list")
            files.extend(page)
            m = _NEXT_LINK.search(resp.headers.get("link", ""))
            url = m.group(1) if m else None
            pages += 1
        return files, False

    @staticmethod
    def _inline_comments_rejected(err: GitHubError) -> bool:
        text = " ".join([err.message] + [str(e) for e in err.errors]).lower()
        return any(k in text for k in ("line", "position", "diff", "path", "comment", "start_line", "side"))

    async def create_pull_review(self, repo: str, number: int, commit_id: str, body: str,
                                 comments: List[Dict[str, Any]], event: str = "COMMENT") -> Dict[str, Any]:
        """One review with inline comments. If GitHub rejects the inline
        comments themselves (a line outside the diff), post the body alone
        with the notes folded in, rather than losing the review. Any other
        422 (spam limits, validation of the body) is final."""
        payload: Dict[str, Any] = {"commit_id": commit_id, "body": body, "event": event}
        if comments:
            payload["comments"] = comments
        try:
            return (await self._request("POST", f"/repos/{repo}/pulls/{number}/reviews", json=payload)).json()
        except GitHubError as e:
            if e.status != 422 or not comments or not self._inline_comments_rejected(e):
                raise
            logger.warning("inline comments rejected, posting body only", repo=repo, pr=number, error=str(e))
            await asyncio.sleep(1)
            folded = body + "\n\n### Notes that could not be attached inline\n\n" + "\n".join(
                f"- `{sanitise(c['path'], 200, code=True)}` line {int(c['line'])}: {c['body']}" for c in comments)
            payload = {"commit_id": commit_id, "body": folded[:60000], "event": event}
            return (await self._request("POST", f"/repos/{repo}/pulls/{number}/reviews", json=payload)).json()
