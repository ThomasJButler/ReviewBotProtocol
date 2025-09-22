"""GitHub API client with rate limiting and authentication."""

import asyncio
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import httpx
import jwt as PyJWT
from github import Github, GithubIntegration
from github.GithubException import GithubException, RateLimitExceededException

from config.settings import settings
from config.logging import get_logger, github_logger
from models.github import PRFile, PRComment, GitHubStatusCheck
from models.api import GitHubRateLimit
from utils.helpers import retry_async

logger = get_logger(__name__)


class GitHubRateLimiter:
    """Rate limiter for GitHub API requests."""

    def __init__(self):
        self.request_counts = {}
        self.reset_times = {}

    async def wait_if_needed(self, resource: str = "core") -> None:
        """Wait if rate limit is exceeded."""
        current_time = time.time()

        if resource in self.reset_times:
            if current_time < self.reset_times[resource]:
                wait_time = self.reset_times[resource] - current_time
                if wait_time > 0:
                    logger.warning(
                        f"Rate limit exceeded for {resource}, waiting {wait_time:.2f}s"
                    )
                    await asyncio.sleep(wait_time)

    def update_rate_limit(self, headers: Dict[str, str], resource: str = "core") -> None:
        """Update rate limit information from API response headers."""
        try:
            remaining = int(headers.get(f"X-RateLimit-Remaining", 0))
            reset_time = int(headers.get(f"X-RateLimit-Reset", 0))

            self.request_counts[resource] = remaining
            self.reset_times[resource] = reset_time

            if remaining < 100:  # Warning threshold
                logger.warning(
                    f"GitHub API rate limit low",
                    resource=resource,
                    remaining=remaining,
                    reset_time=datetime.fromtimestamp(reset_time)
                )

        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse rate limit headers: {e}")


class GitHubClient:
    """GitHub API client with authentication and rate limiting."""

    def __init__(self, installation_id: Optional[int] = None):
        self.installation_id = installation_id
        self.rate_limiter = GitHubRateLimiter()
        self._github_integration = None
        self._github_instance = None
        self._access_token = None
        self._token_expires_at = None

        # Initialize GitHub integration
        if settings.GITHUB_APP_ID and settings.GITHUB_PRIVATE_KEY:
            self._github_integration = GithubIntegration(
                settings.GITHUB_APP_ID,
                settings.GITHUB_PRIVATE_KEY
            )

    async def _get_access_token(self) -> str:
        """Get or refresh GitHub App access token."""
        if (self._access_token and self._token_expires_at and
                datetime.utcnow() < self._token_expires_at - timedelta(minutes=5)):
            return self._access_token

        if not self._github_integration or not self.installation_id:
            raise ValueError("GitHub integration not configured or installation_id missing")

        try:
            # Get installation access token
            installation = self._github_integration.get_installation(self.installation_id)
            access_token = installation.get_access_token()

            self._access_token = access_token.token
            self._token_expires_at = access_token.expires_at

            logger.info(
                "GitHub access token refreshed",
                installation_id=self.installation_id,
                expires_at=self._token_expires_at
            )

            return self._access_token

        except Exception as e:
            logger.error(f"Failed to get GitHub access token: {str(e)}")
            raise

    async def _get_github_instance(self) -> Github:
        """Get authenticated GitHub instance."""
        if (self._github_instance and self._token_expires_at and
                datetime.utcnow() < self._token_expires_at - timedelta(minutes=5)):
            return self._github_instance

        access_token = await self._get_access_token()
        self._github_instance = Github(access_token)

        return self._github_instance

    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated HTTP request to GitHub API."""
        await self.rate_limiter.wait_if_needed()

        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **kwargs.pop("headers", {})
        }

        start_time = time.time()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=f"https://api.github.com{url}",
                    headers=headers,
                    timeout=30.0,
                    **kwargs
                )

                duration = time.time() - start_time

                # Update rate limit info
                self.rate_limiter.update_rate_limit(dict(response.headers))

                # Log request
                github_logger.api_request(
                    method=method,
                    endpoint=url,
                    status_code=response.status_code,
                    duration=duration,
                    rate_limit_remaining=response.headers.get("X-RateLimit-Remaining")
                )

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                github_logger.api_error(
                    method=method,
                    endpoint=url,
                    status_code=e.response.status_code,
                    error=str(e)
                )

                if e.response.status_code == 403:
                    # Likely rate limit exceeded
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        await asyncio.sleep(int(retry_after))

                raise
            except Exception as e:
                github_logger.api_error(
                    method=method,
                    endpoint=url,
                    status_code=0,
                    error=str(e)
                )
                raise

    async def get_pr_files(self, repo_full_name: str, pr_number: int) -> List[PRFile]:
        """Get files changed in a pull request."""
        try:
            url = f"/repos/{repo_full_name}/pulls/{pr_number}/files"
            response = await self._make_request("GET", url)

            files = []
            for file_data in response:
                # Get file patch content if available
                patch = file_data.get("patch")

                # Skip binary files
                if not patch and file_data.get("status") != "removed":
                    continue

                pr_file = PRFile(
                    filename=file_data["filename"],
                    status=file_data["status"],
                    additions=file_data["additions"],
                    deletions=file_data["deletions"],
                    changes=file_data["changes"],
                    blob_url=file_data["blob_url"],
                    raw_url=file_data["raw_url"],
                    contents_url=file_data["contents_url"],
                    patch=patch,
                    previous_filename=file_data.get("previous_filename")
                )
                files.append(pr_file)

            logger.info(
                f"Retrieved {len(files)} files for PR #{pr_number}",
                repository=repo_full_name,
                pr_number=pr_number
            )

            return files

        except Exception as e:
            logger.error(
                f"Failed to get PR files: {str(e)}",
                repository=repo_full_name,
                pr_number=pr_number
            )
            raise

    async def post_review_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
        commit_sha: str,
        path: str,
        line: int,
        side: str = "RIGHT"
    ) -> Dict[str, Any]:
        """Post an inline review comment on a pull request."""
        try:
            url = f"/repos/{repo_full_name}/pulls/{pr_number}/comments"
            data = {
                "body": body,
                "commit_id": commit_sha,
                "path": path,
                "line": line,
                "side": side
            }

            response = await self._make_request("POST", url, json=data)

            github_logger.comment_posted(
                repo_full_name,
                pr_number,
                response["id"],
                line
            )

            logger.info(
                "Posted review comment",
                repository=repo_full_name,
                pr_number=pr_number,
                path=path,
                line=line,
                comment_id=response["id"]
            )

            return response

        except Exception as e:
            logger.error(
                f"Failed to post review comment: {str(e)}",
                repository=repo_full_name,
                pr_number=pr_number,
                path=path,
                line=line
            )
            raise

    async def post_pr_review(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Post a pull request review."""
        try:
            url = f"/repos/{repo_full_name}/pulls/{pr_number}/reviews"
            data = {
                "body": body,
                "event": event
            }

            if comments:
                data["comments"] = comments

            response = await self._make_request("POST", url, json=data)

            logger.info(
                "Posted PR review",
                repository=repo_full_name,
                pr_number=pr_number,
                event=event,
                review_id=response["id"],
                comments_count=len(comments) if comments else 0
            )

            return response

        except Exception as e:
            logger.error(
                f"Failed to post PR review: {str(e)}",
                repository=repo_full_name,
                pr_number=pr_number,
                event=event
            )
            raise

    async def create_status_check(
        self,
        repo_full_name: str,
        commit_sha: str,
        state: str,
        description: str,
        context: str = "git-review-assistant",
        target_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a status check on a commit."""
        try:
            url = f"/repos/{repo_full_name}/statuses/{commit_sha}"
            data = {
                "state": state,
                "description": description,
                "context": context
            }

            if target_url:
                data["target_url"] = target_url

            response = await self._make_request("POST", url, json=data)

            logger.info(
                "Created status check",
                repository=repo_full_name,
                commit_sha=commit_sha[:8],
                state=state,
                context=context
            )

            return response

        except Exception as e:
            logger.error(
                f"Failed to create status check: {str(e)}",
                repository=repo_full_name,
                commit_sha=commit_sha[:8],
                state=state
            )
            raise

    async def get_pr_info(self, repo_full_name: str, pr_number: int) -> Dict[str, Any]:
        """Get pull request information."""
        try:
            url = f"/repos/{repo_full_name}/pulls/{pr_number}"
            response = await self._make_request("GET", url)

            logger.info(
                "Retrieved PR info",
                repository=repo_full_name,
                pr_number=pr_number,
                state=response["state"]
            )

            return response

        except Exception as e:
            logger.error(
                f"Failed to get PR info: {str(e)}",
                repository=repo_full_name,
                pr_number=pr_number
            )
            raise

    async def get_file_content(
        self,
        repo_full_name: str,
        path: str,
        ref: str = "main"
    ) -> str:
        """Get file content from repository."""
        try:
            url = f"/repos/{repo_full_name}/contents/{path}"
            response = await self._make_request("GET", url, params={"ref": ref})

            if response["type"] == "file":
                import base64
                return base64.b64decode(response["content"]).decode("utf-8")
            else:
                raise ValueError(f"Path {path} is not a file")

        except Exception as e:
            logger.error(
                f"Failed to get file content: {str(e)}",
                repository=repo_full_name,
                path=path,
                ref=ref
            )
            raise

    async def get_rate_limit_status(self) -> GitHubRateLimit:
        """Get current rate limit status."""
        try:
            response = await self._make_request("GET", "/rate_limit")
            core_data = response["resources"]["core"]

            return GitHubRateLimit(
                limit=core_data["limit"],
                remaining=core_data["remaining"],
                reset=datetime.fromtimestamp(core_data["reset"]),
                used=core_data["used"],
                resource="core"
            )

        except Exception as e:
            logger.error(f"Failed to get rate limit status: {str(e)}")
            raise

    async def get_user_repositories(self, per_page: int = 30, page: int = 1) -> List[Dict[str, Any]]:
        """Get repositories for the authenticated user."""
        try:
            github = await self._get_github_instance()
            user = github.get_user()

            repos = []
            for repo in user.get_repos(per_page=per_page):
                repos.append({
                    "id": repo.id,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "description": repo.description,
                    "private": repo.private,
                    "fork": repo.fork,
                    "language": repo.language,
                    "default_branch": repo.default_branch,
                    "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                    "url": repo.html_url
                })

                if len(repos) >= per_page:
                    break

            logger.info(f"Retrieved {len(repos)} repositories for user")
            return repos

        except Exception as e:
            logger.error(f"Failed to get user repositories: {str(e)}")
            raise

    async def get_repository_pulls(
        self,
        repo_full_name: str,
        state: str = "open",
        per_page: int = 30,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """Get pull requests for a repository."""
        try:
            url = f"/repos/{repo_full_name}/pulls"
            params = {
                "state": state,
                "per_page": per_page,
                "page": page,
                "sort": "updated",
                "direction": "desc"
            }

            response = await self._make_request("GET", url, params=params)

            pulls = []
            for pr_data in response:
                pulls.append({
                    "id": pr_data["id"],
                    "number": pr_data["number"],
                    "title": pr_data["title"],
                    "description": pr_data["body"] or "",
                    "author": pr_data["user"]["login"],
                    "state": pr_data["state"],
                    "draft": pr_data["draft"],
                    "repository": repo_full_name,
                    "branch": pr_data["head"]["ref"],
                    "baseBranch": pr_data["base"]["ref"],
                    "createdAt": pr_data["created_at"],
                    "updatedAt": pr_data["updated_at"],
                    "labels": [label["name"] for label in pr_data["labels"]],
                    "changedFiles": pr_data["changed_files"],
                    "additions": pr_data["additions"],
                    "deletions": pr_data["deletions"],
                    "commits": pr_data["commits"],
                    "url": pr_data["html_url"],
                    "head_sha": pr_data["head"]["sha"]
                })

            logger.info(
                f"Retrieved {len(pulls)} pull requests",
                repository=repo_full_name,
                state=state
            )

            return pulls

        except Exception as e:
            logger.error(
                f"Failed to get repository pulls: {str(e)}",
                repository=repo_full_name,
                state=state
            )
            raise

    async def search_user_pulls(
        self,
        query: str = "",
        state: str = "open",
        per_page: int = 30
    ) -> List[Dict[str, Any]]:
        """Search pull requests for the authenticated user across all repositories."""
        try:
            github = await self._get_github_instance()
            user = github.get_user()
            username = user.login

            # Build search query
            search_query = f"author:{username} type:pr"
            if state != "all":
                search_query += f" state:{state}"
            if query:
                search_query += f" {query}"

            url = "/search/issues"
            params = {
                "q": search_query,
                "per_page": per_page,
                "sort": "updated",
                "order": "desc"
            }

            response = await self._make_request("GET", url, params=params)

            pulls = []
            for item in response.get("items", []):
                # Extract repository name from URL
                repo_full_name = "/".join(item["repository_url"].split("/")[-2:])

                pulls.append({
                    "id": item["id"],
                    "number": item["number"],
                    "title": item["title"],
                    "description": item["body"] or "",
                    "author": item["user"]["login"],
                    "state": item["state"],
                    "draft": item.get("draft", False),
                    "repository": repo_full_name,
                    "createdAt": item["created_at"],
                    "updatedAt": item["updated_at"],
                    "labels": [label["name"] for label in item["labels"]],
                    "url": item["html_url"]
                })

            logger.info(
                f"Found {len(pulls)} pull requests in search",
                query=search_query,
                total=response.get("total_count", 0)
            )

            return pulls

        except Exception as e:
            logger.error(f"Failed to search user pulls: {str(e)}")
            raise


# Health check functions for main app

async def get_github_health() -> Dict[str, Any]:
    """Check GitHub API health and connectivity."""
    try:
        # Simple rate limit check
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/rate_limit",
                timeout=10.0
            )

        if response.status_code == 200:
            data = response.json()
            return {
                "accessible": True,
                "rate_limit": data.get("resources", {}).get("core", {}),
                "status": "healthy"
            }
        else:
            return {
                "accessible": False,
                "status": "unhealthy",
                "error": f"HTTP {response.status_code}"
            }

    except Exception as e:
        return {
            "accessible": False,
            "status": "unhealthy",
            "error": str(e)
        }


async def validate_github_config() -> Dict[str, Any]:
    """Validate GitHub configuration."""
    issues = []

    if not settings.GITHUB_APP_ID:
        issues.append("GITHUB_APP_ID not configured")

    if not settings.GITHUB_PRIVATE_KEY:
        issues.append("GITHUB_PRIVATE_KEY not configured")

    if not settings.GITHUB_WEBHOOK_SECRET:
        issues.append("GITHUB_WEBHOOK_SECRET not configured")

    # Test JWT generation if config looks good
    if not issues:
        try:
            payload = {
                "iat": int(time.time()),
                "exp": int(time.time()) + (10 * 60),  # 10 minutes
                "iss": settings.GITHUB_APP_ID
            }
            PyJWT.encode(payload, settings.GITHUB_PRIVATE_KEY, algorithm="RS256")
        except Exception as e:
            issues.append(f"Failed to generate JWT: {str(e)}")

    return {
        "valid": len(issues) == 0,
        "issues": issues
    }