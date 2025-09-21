"""GitHub API handlers for retrieving repositories and pull requests."""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from services.github_client import GitHubClient
from config.logging import get_logger
from models.api import APIResponse

logger = get_logger(__name__)

github_router = APIRouter()


class GitHubAuthDependency:
    """Dependency to get GitHub client with user authentication."""

    async def __call__(self, installation_id: Optional[int] = None) -> GitHubClient:
        """Get authenticated GitHub client."""
        # TODO: Implement proper user authentication
        # For now, use a default installation ID from settings
        from config.settings import settings

        if not installation_id and hasattr(settings, 'GITHUB_INSTALLATION_ID'):
            installation_id = settings.GITHUB_INSTALLATION_ID
        elif not installation_id:
            # This should be extracted from user session/JWT token
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub authentication required"
            )

        return GitHubClient(installation_id=installation_id)


get_github_client = GitHubAuthDependency()


class RepositoryResponse(BaseModel):
    """Repository information response."""
    id: int
    name: str
    full_name: str
    description: Optional[str]
    private: bool
    fork: bool
    language: Optional[str]
    default_branch: str
    updated_at: Optional[str]
    url: str


class PullRequestResponse(BaseModel):
    """Pull request information response."""
    id: int
    number: int
    title: str
    description: str
    author: str
    state: str
    draft: bool
    repository: str
    branch: str
    baseBranch: str
    createdAt: str
    updatedAt: str
    labels: List[str]
    changedFiles: int
    additions: int
    deletions: int
    commits: int
    url: str
    head_sha: Optional[str] = None


@github_router.get("/repositories", response_model=APIResponse[List[RepositoryResponse]])
async def get_user_repositories(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    github_client: GitHubClient = Depends(get_github_client)
):
    """Get repositories for the authenticated user."""
    try:
        logger.info("Fetching user repositories", page=page, per_page=per_page)

        repositories = await github_client.get_user_repositories(
            page=page,
            per_page=per_page
        )

        return APIResponse(
            success=True,
            data=repositories,
            metadata={
                "page": page,
                "per_page": per_page,
                "total": len(repositories)
            }
        )

    except Exception as e:
        logger.error(f"Failed to fetch repositories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch repositories"
        )


@github_router.get("/repositories/{repo_full_name}/pulls", response_model=APIResponse[List[PullRequestResponse]])
async def get_repository_pulls(
    repo_full_name: str,
    state: str = Query("open", regex="^(open|closed|all)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    github_client: GitHubClient = Depends(get_github_client)
):
    """Get pull requests for a specific repository."""
    try:
        logger.info(
            "Fetching repository pull requests",
            repository=repo_full_name,
            state=state,
            page=page,
            per_page=per_page
        )

        pulls = await github_client.get_repository_pulls(
            repo_full_name=repo_full_name,
            state=state,
            page=page,
            per_page=per_page
        )

        return APIResponse(
            success=True,
            data=pulls,
            metadata={
                "repository": repo_full_name,
                "state": state,
                "page": page,
                "per_page": per_page,
                "total": len(pulls)
            }
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch repository pulls: {str(e)}",
            repository=repo_full_name,
            state=state
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch pull requests"
        )


@github_router.get("/pulls/search", response_model=APIResponse[List[PullRequestResponse]])
async def search_user_pulls(
    query: str = Query("", description="Search query for pull requests"),
    state: str = Query("open", regex="^(open|closed|all)$"),
    per_page: int = Query(30, ge=1, le=100),
    github_client: GitHubClient = Depends(get_github_client)
):
    """Search pull requests for the authenticated user across all repositories."""
    try:
        logger.info(
            "Searching user pull requests",
            query=query,
            state=state,
            per_page=per_page
        )

        pulls = await github_client.search_user_pulls(
            query=query,
            state=state,
            per_page=per_page
        )

        return APIResponse(
            success=True,
            data=pulls,
            metadata={
                "query": query,
                "state": state,
                "per_page": per_page,
                "total": len(pulls)
            }
        )

    except Exception as e:
        logger.error(
            f"Failed to search user pulls: {str(e)}",
            query=query,
            state=state
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search pull requests"
        )


@github_router.get("/pulls/{repo_full_name}/{pr_number}", response_model=APIResponse[Dict[str, Any]])
async def get_pull_request_details(
    repo_full_name: str,
    pr_number: int,
    github_client: GitHubClient = Depends(get_github_client)
):
    """Get detailed information about a specific pull request."""
    try:
        logger.info(
            "Fetching pull request details",
            repository=repo_full_name,
            pr_number=pr_number
        )

        # Get PR info and files
        pr_info = await github_client.get_pr_info(repo_full_name, pr_number)
        pr_files = await github_client.get_pr_files(repo_full_name, pr_number)

        # Combine the data
        detailed_pr = {
            **pr_info,
            "files": [
                {
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "changes": f.changes,
                    "patch": f.patch,
                    "blob_url": f.blob_url,
                    "raw_url": f.raw_url
                }
                for f in pr_files
            ]
        }

        return APIResponse(
            success=True,
            data=detailed_pr,
            metadata={
                "repository": repo_full_name,
                "pr_number": pr_number,
                "files_count": len(pr_files)
            }
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch pull request details: {str(e)}",
            repository=repo_full_name,
            pr_number=pr_number
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch pull request details"
        )


@github_router.get("/rate-limit")
async def get_rate_limit_status(
    github_client: GitHubClient = Depends(get_github_client)
):
    """Get current GitHub API rate limit status."""
    try:
        rate_limit = await github_client.get_rate_limit_status()

        return APIResponse(
            success=True,
            data={
                "limit": rate_limit.limit,
                "remaining": rate_limit.remaining,
                "reset": rate_limit.reset.isoformat(),
                "used": rate_limit.used,
                "resource": rate_limit.resource
            }
        )

    except Exception as e:
        logger.error(f"Failed to get rate limit status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get rate limit status"
        )