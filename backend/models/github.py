"""Pydantic models for the pull_request webhook payload. Only the fields the
handler needs are required; GitHub sends far more and extras are ignored."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PRAction(str, Enum):
    OPENED = "opened"
    CLOSED = "closed"
    REOPENED = "reopened"
    SYNCHRONIZE = "synchronize"
    EDITED = "edited"
    READY_FOR_REVIEW = "ready_for_review"
    CONVERTED_TO_DRAFT = "converted_to_draft"
    LABELED = "labeled"
    UNLABELED = "unlabeled"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_REQUEST_REMOVED = "review_request_removed"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    AUTO_MERGE_ENABLED = "auto_merge_enabled"
    AUTO_MERGE_DISABLED = "auto_merge_disabled"
    ENQUEUED = "enqueued"
    DEQUEUED = "dequeued"
    MILESTONED = "milestoned"
    DEMILESTONED = "demilestoned"


REVIEW_TRIGGERS = {PRAction.OPENED, PRAction.SYNCHRONIZE, PRAction.REOPENED, PRAction.READY_FOR_REVIEW}


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class GitHubUser(_Loose):
    id: int
    login: str


class GitHubRepository(_Loose):
    id: int
    full_name: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    private: bool = False
    fork: bool = False


class GitHubInstallation(_Loose):
    id: int


class GitRef(_Loose):
    ref: str
    sha: str
    repo: Optional[GitHubRepository] = None


class PullRequest(_Loose):
    number: int
    title: str = ""
    draft: bool = False
    state: str = "open"
    head: GitRef
    base: GitRef
    user: GitHubUser


class PRWebhookPayload(_Loose):
    action: str
    number: int
    pull_request: PullRequest
    repository: GitHubRepository
    installation: GitHubInstallation
    sender: GitHubUser

    @property
    def is_fork(self) -> bool:
        """Fail closed: a missing head repository (the fork was deleted) counts as a fork."""
        head_repo = self.pull_request.head.repo
        if head_repo is None:
            return True
        return head_repo.full_name.lower() != self.repository.full_name.lower()

    @property
    def fork_repo(self) -> Optional[str]:
        if not self.is_fork:
            return None
        head_repo = self.pull_request.head.repo
        return head_repo.full_name if head_repo else "(deleted fork)"
