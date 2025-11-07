"""Pydantic models for review data and API responses."""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import uuid


class ReviewStatus(str, Enum):
    """Review status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewType(str, Enum):
    """Review type enumeration."""
    MANUAL = "manual"  # Manual code review
    PR_WEBHOOK = "pr_webhook"  # Triggered by PR webhook
    SCHEDULED = "scheduled"  # Scheduled review


class SeverityLevel(str, Enum):
    """Issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(str, Enum):
    """Issue category enumeration."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    TESTING = "testing"


# Base Models

class ReviewIssue(BaseModel):
    """Base model for review issues."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: IssueCategory
    severity: SeverityLevel
    title: str
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    rule_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('line_number', 'column_number')
    def validate_positive_numbers(cls, v):
        """Ensure line and column numbers are positive."""
        if v is not None and v <= 0:
            raise ValueError("Line and column numbers must be positive")
        return v


class ReviewMetrics(BaseModel):
    """Review metrics model."""
    total_files: int = 0
    files_reviewed: int = 0
    total_lines: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    cyclomatic_complexity: Optional[float] = None
    test_coverage: Optional[float] = None
    code_duplication: Optional[float] = None
    maintainability_index: Optional[float] = None


class ReviewConfiguration(BaseModel):
    """Review configuration model."""
    include_security: bool = True
    include_performance: bool = True
    include_quality: bool = True
    include_style: bool = False
    include_documentation: bool = False
    include_testing: bool = False
    max_issues_per_file: int = 10
    exclude_patterns: List[str] = []
    custom_rules: Dict[str, Any] = {}


class CodeReview(BaseModel):
    """Main code review model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ReviewType
    status: ReviewStatus = ReviewStatus.PENDING

    # Repository information
    repository: Optional[str] = None
    pr_number: Optional[int] = None
    commit_sha: Optional[str] = None

    # Review configuration
    configuration: ReviewConfiguration = Field(default_factory=ReviewConfiguration)

    # Review results
    issues: List[ReviewIssue] = []
    metrics: ReviewMetrics = Field(default_factory=ReviewMetrics)
    overall_score: float = 0.0

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: Optional[str] = None

    # Processing information
    processing_time: Optional[float] = None  # seconds
    ai_model_used: Optional[str] = None
    error_message: Optional[str] = None

    # GitHub integration
    github_check_run_id: Optional[int] = None
    github_status_context: str = "git-review-assistant"
    comments_posted: int = 0

    @property
    def duration(self) -> Optional[float]:
        """Calculate review duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def issues_by_severity(self) -> Dict[SeverityLevel, int]:
        """Count issues by severity level."""
        counts = {severity: 0 for severity in SeverityLevel}
        for issue in self.issues:
            counts[issue.severity] += 1
        return counts

    @property
    def issues_by_category(self) -> Dict[IssueCategory, int]:
        """Count issues by category."""
        counts = {category: 0 for category in IssueCategory}
        for issue in self.issues:
            counts[issue.category] += 1
        return counts

    @property
    def has_critical_issues(self) -> bool:
        """Check if review has critical issues."""
        return any(issue.severity == SeverityLevel.CRITICAL for issue in self.issues)

    @property
    def recommendation(self) -> str:
        """Get review recommendation based on issues."""
        critical_count = self.issues_by_severity[SeverityLevel.CRITICAL]
        high_count = self.issues_by_severity[SeverityLevel.HIGH]

        if critical_count > 0:
            return "reject"
        elif high_count > 3:
            return "request_changes"
        elif self.overall_score >= 8.0:
            return "approve"
        else:
            return "comment"


# API Request Models

class ManualReviewRequest(BaseModel):
    """Request model for manual code review."""
    code: str
    language: Optional[str] = None
    filename: Optional[str] = None
    configuration: Optional[ReviewConfiguration] = None


class FileReviewRequest(BaseModel):
    """Request model for file-based review."""
    files: List[Dict[str, str]]  # List of {filename: content} pairs
    configuration: Optional[ReviewConfiguration] = None


class PRReviewRequest(BaseModel):
    """Request model for PR review."""
    repository: str
    pr_number: int
    force_refresh: bool = False
    configuration: Optional[ReviewConfiguration] = None


# API Response Models

class ReviewResponse(BaseModel):
    """Response model for review operations."""
    review_id: str
    status: ReviewStatus
    message: str
    created_at: datetime
    estimated_completion: Optional[datetime] = None


class ReviewResultResponse(BaseModel):
    """Response model for review results."""
    review: CodeReview
    summary: str
    recommendations: List[str] = []


class ReviewListResponse(BaseModel):
    """Response model for review listing."""
    reviews: List[CodeReview]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class ReviewStatsResponse(BaseModel):
    """Response model for review statistics."""
    total_reviews: int
    completed_reviews: int
    failed_reviews: int
    avg_processing_time: float
    avg_score: float
    common_issues: List[Dict[str, Any]]
    reviews_by_repository: Dict[str, int]
    reviews_by_date: Dict[str, int]


class ReviewHistoryItem(BaseModel):
    """Model for review history item."""
    id: str
    type: str
    status: str
    repository: Optional[str] = None
    pr_number: Optional[int] = None
    overall_score: Optional[float] = None
    letter_grade: Optional[str] = None
    total_issues: int = 0
    security_issues: int = 0
    performance_issues: int = 0
    quality_issues: int = 0
    created_at: datetime
    processing_time: Optional[float] = None
    ai_model_used: Optional[str] = None
    code_suggestions: List[Any] = []
    priority_fixes: List[Any] = []


class ReviewHistoryResponse(BaseModel):
    """Response model for review history."""
    reviews: List[ReviewHistoryItem]
    pagination: Dict[str, Any]
    filters_applied: Dict[str, Any]


class UserStatsResponse(BaseModel):
    """Response model for user statistics."""
    user_id: str
    total_reviews: int
    average_score: float
    total_issues_found: int
    improvement_trend: float
    top_issues: List[Dict[str, Any]]
    repositories_reviewed: List[str]
    review_frequency: str
    best_review: Optional[float] = None
    worst_review: Optional[float] = None
    recent_activity: Dict[str, int]


class QueueStatusResponse(BaseModel):
    """Response model for queue status."""
    queue_stats: Dict[str, Any]
    worker_status: str
    timestamp: datetime


# LangChain Integration Models

class LangChainPrompt(BaseModel):
    """Model for LangChain prompts."""
    name: str
    template: str
    input_variables: List[str]
    output_parser: Optional[str] = None


class LangChainChainConfig(BaseModel):
    """Configuration for LangChain chains."""
    name: str
    chain_type: str
    model_name: str = "gpt-4o"
    temperature: float = 0.1
    max_tokens: int = 4000
    prompts: List[LangChainPrompt]
    memory_type: Optional[str] = None


class AIAnalysisResult(BaseModel):
    """Result from AI analysis."""
    chain_name: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    processing_time: float
    issues_found: List[ReviewIssue]
    summary: str
    confidence_score: float
    model_version: str


# Database Models (for ORM mapping)

class ReviewDB(BaseModel):
    """Database model for reviews."""
    id: str
    type: str
    status: str
    repository: Optional[str] = None
    pr_number: Optional[int] = None
    commit_sha: Optional[str] = None
    configuration: str  # JSON serialized
    issues: str  # JSON serialized
    metrics: str  # JSON serialized
    overall_score: float
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: Optional[str] = None
    processing_time: Optional[float] = None
    ai_model_used: Optional[str] = None
    error_message: Optional[str] = None
    github_check_run_id: Optional[int] = None
    comments_posted: int = 0

    class Config:
        orm_mode = True


class ReviewIssueDB(BaseModel):
    """Database model for review issues."""
    id: str
    review_id: str
    category: str
    severity: str
    title: str
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    rule_id: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True