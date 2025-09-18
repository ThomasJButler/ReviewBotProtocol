"""Pydantic models for GitHub webhook payloads and API responses."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class GitHubEventType(str, Enum):
    """GitHub webhook event types."""
    PULL_REQUEST = "pull_request"
    PULL_REQUEST_REVIEW = "pull_request_review"
    PULL_REQUEST_REVIEW_COMMENT = "pull_request_review_comment"
    PUSH = "push"
    ISSUE = "issues"
    ISSUE_COMMENT = "issue_comment"


class PRAction(str, Enum):
    """Pull request action types."""
    OPENED = "opened"
    CLOSED = "closed"
    REOPENED = "reopened"
    SYNCHRONIZE = "synchronize"
    EDITED = "edited"
    READY_FOR_REVIEW = "ready_for_review"
    CONVERTED_TO_DRAFT = "converted_to_draft"


class PRState(str, Enum):
    """Pull request states."""
    OPEN = "open"
    CLOSED = "closed"


class GitHubUser(BaseModel):
    """GitHub user model."""
    id: int
    login: str
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    type: Optional[str] = None


class GitHubRepository(BaseModel):
    """GitHub repository model."""
    id: int
    name: str
    full_name: str
    private: bool
    html_url: str
    description: Optional[str] = None
    fork: bool = False
    default_branch: str = "main"
    owner: GitHubUser


class GitHubInstallation(BaseModel):
    """GitHub App installation model."""
    id: int
    account: GitHubUser


class GitRef(BaseModel):
    """Git reference model."""
    ref: str
    sha: str
    label: Optional[str] = None
    repo: Optional[GitHubRepository] = None
    user: Optional[GitHubUser] = None


class PullRequest(BaseModel):
    """Pull request model."""
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: PRState
    draft: bool = False
    merged: bool = False
    mergeable: Optional[bool] = None
    mergeable_state: Optional[str] = None
    html_url: str
    diff_url: str
    patch_url: str
    head: GitRef
    base: GitRef
    user: GitHubUser
    created_at: datetime
    updated_at: datetime
    merged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    assignees: List[GitHubUser] = []
    requested_reviewers: List[GitHubUser] = []
    labels: List[Dict[str, Any]] = []
    commits: Optional[int] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None
    changed_files: Optional[int] = None


class PRWebhookPayload(BaseModel):
    """Pull request webhook payload model."""
    action: PRAction
    number: int
    pull_request: PullRequest
    repository: GitHubRepository
    installation: GitHubInstallation
    sender: GitHubUser


class PRFile(BaseModel):
    """Pull request file model."""
    filename: str
    status: str  # added, removed, modified, renamed
    additions: int
    deletions: int
    changes: int
    blob_url: str
    raw_url: str
    contents_url: str
    patch: Optional[str] = None  # Git diff patch
    previous_filename: Optional[str] = None  # For renamed files

    @field_validator('patch')
    @classmethod
    def validate_patch(cls, v):
        """Ensure patch content is not too large."""
        if v and len(v) > 100000:  # 100KB limit
            return v[:100000] + "\n... (truncated)"
        return v


class PRComment(BaseModel):
    """Pull request comment model."""
    id: int
    body: str
    user: GitHubUser
    created_at: datetime
    updated_at: datetime
    html_url: str
    pull_request_url: str
    position: Optional[int] = None  # Line position in diff
    original_position: Optional[int] = None
    commit_id: Optional[str] = None
    original_commit_id: Optional[str] = None
    in_reply_to_id: Optional[int] = None
    path: Optional[str] = None  # File path for inline comments
    line: Optional[int] = None  # Line number for inline comments
    side: Optional[str] = None  # LEFT or RIGHT for inline comments


class PRReview(BaseModel):
    """Pull request review model."""
    id: int
    user: GitHubUser
    body: Optional[str] = None
    state: str  # PENDING, APPROVED, CHANGES_REQUESTED, COMMENTED
    html_url: str
    pull_request_url: str
    submitted_at: Optional[datetime] = None
    commit_id: str


class GitHubStatusCheck(BaseModel):
    """GitHub status check model."""
    state: str  # pending, success, failure, error
    target_url: Optional[str] = None
    description: Optional[str] = None
    context: str = "git-review-assistant"


class GitHubCheckRun(BaseModel):
    """GitHub check run model."""
    name: str
    head_sha: str
    status: str  # queued, in_progress, completed
    conclusion: Optional[str] = None  # success, failure, neutral, cancelled, timed_out, action_required
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output: Optional[Dict[str, Any]] = None
    details_url: Optional[str] = None


class WebhookDelivery(BaseModel):
    """Webhook delivery tracking model."""
    id: str
    event_type: GitHubEventType
    delivery_id: str
    received_at: datetime
    processed_at: Optional[datetime] = None
    status: str = "pending"  # pending, processing, completed, failed
    error_message: Optional[str] = None
    repository: str
    pr_number: Optional[int] = None


# API Request/Response Models

class CreateCommentRequest(BaseModel):
    """Request model for creating PR comments."""
    body: str
    path: Optional[str] = None
    line: Optional[int] = None
    side: str = "RIGHT"
    commit_sha: Optional[str] = None


class CreateReviewRequest(BaseModel):
    """Request model for creating PR reviews."""
    body: Optional[str] = None
    event: str = "COMMENT"  # APPROVE, REQUEST_CHANGES, COMMENT
    comments: List[CreateCommentRequest] = []


class PRAnalysisRequest(BaseModel):
    """Request model for PR analysis."""
    repository: str
    pr_number: int
    include_security: bool = True
    include_performance: bool = True
    include_quality: bool = True
    force_refresh: bool = False


class PRAnalysisResponse(BaseModel):
    """Response model for PR analysis."""
    repository: str
    pr_number: int
    analysis_id: str
    status: str  # pending, in_progress, completed, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    summary: Optional[str] = None
    score: Optional[float] = None
    issues_found: int = 0
    comments_posted: int = 0
    error_message: Optional[str] = None


class SecurityIssue(BaseModel):
    """Security issue model."""
    type: str
    severity: str  # critical, high, medium, low
    message: str
    file_path: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    cwe_id: Optional[str] = None  # Common Weakness Enumeration ID


class PerformanceIssue(BaseModel):
    """Performance issue model."""
    type: str
    severity: str  # high, medium, low
    message: str
    file_path: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    impact: Optional[str] = None


class QualityIssue(BaseModel):
    """Code quality issue model."""
    type: str
    severity: str  # warning, info
    message: str
    file_path: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    rule_id: Optional[str] = None


class ReviewSummary(BaseModel):
    """Review summary model."""
    total_files: int
    files_reviewed: int
    total_lines: int
    lines_added: int
    lines_deleted: int
    security_issues: List[SecurityIssue] = []
    performance_issues: List[PerformanceIssue] = []
    quality_issues: List[QualityIssue] = []
    overall_score: float
    recommendation: str  # approve, request_changes, comment
    processing_time: float  # seconds