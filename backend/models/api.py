"""Pydantic models for API responses and common structures."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class APIStatus(str, Enum):
    """API response status enumeration."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class ErrorCode(str, Enum):
    """Error code enumeration."""
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    NOT_FOUND = "not_found"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    GITHUB_API_ERROR = "github_api_error"
    AI_SERVICE_ERROR = "ai_service_error"
    INTERNAL_ERROR = "internal_error"
    WEBHOOK_VERIFICATION_FAILED = "webhook_verification_failed"
    INVALID_PAYLOAD = "invalid_payload"


class APIError(BaseModel):
    """API error model."""
    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class APIResponse(BaseModel):
    """Generic API response model."""
    status: APIStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[APIError]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


class HealthCheck(BaseModel):
    """Health check response model."""
    status: str
    version: str
    timestamp: float
    uptime: Optional[float] = None
    checks: Optional[Dict[str, Dict[str, Any]]] = None


class PaginationMeta(BaseModel):
    """Pagination metadata model."""
    page: int = 1
    per_page: int = 20
    total: int = 0
    pages: int = 0
    has_next: bool = False
    has_prev: bool = False


class PaginatedResponse(BaseModel):
    """Paginated response model."""
    items: List[Dict[str, Any]]
    meta: PaginationMeta


class RateLimitInfo(BaseModel):
    """Rate limit information model."""
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None


class WebhookResponse(BaseModel):
    """Webhook response model."""
    status: APIStatus
    message: str
    event_type: str
    event_id: str
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time: Optional[float] = None
    actions_taken: Optional[List[str]] = None


class AuthToken(BaseModel):
    """Authentication token model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: datetime
    scope: Optional[str] = None
    refresh_token: Optional[str] = None


class UserInfo(BaseModel):
    """User information model."""
    id: str
    username: str
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    github_id: Optional[int] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True


class RepositoryInfo(BaseModel):
    """Repository information model."""
    id: int
    name: str
    full_name: str
    private: bool
    description: Optional[str] = None
    html_url: str
    clone_url: str
    default_branch: str
    language: Optional[str] = None
    size: int
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    created_at: datetime
    updated_at: datetime
    pushed_at: Optional[datetime] = None
    owner: Dict[str, Any]


class PRInfo(BaseModel):
    """Pull request information model."""
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    html_url: str
    diff_url: str
    author: str
    created_at: datetime
    updated_at: datetime
    mergeable: Optional[bool] = None
    draft: bool = False
    commits: int
    additions: int
    deletions: int
    changed_files: int


class ReviewProgress(BaseModel):
    """Review progress model for real-time updates."""
    review_id: str
    status: str
    progress_percentage: float = 0.0
    current_step: str
    steps_completed: int = 0
    total_steps: int = 0
    estimated_completion: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class MetricsResponse(BaseModel):
    """Metrics response model."""
    requests_total: int = 0
    requests_failed: int = 0
    reviews_completed: int = 0
    reviews_failed: int = 0
    avg_response_time: float = 0.0
    avg_review_time: float = 0.0
    github_api_calls: int = 0
    ai_api_calls: int = 0
    uptime: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0


class ConfigurationResponse(BaseModel):
    """Configuration response model."""
    app_name: str
    version: str
    environment: str
    features: Dict[str, bool]
    limits: Dict[str, int]
    github_app_installed: bool
    ai_service_available: bool


class ValidationError(BaseModel):
    """Validation error detail model."""
    field: str
    message: str
    invalid_value: Optional[Any] = None


class BatchOperationResponse(BaseModel):
    """Batch operation response model."""
    total_items: int
    successful_items: int
    failed_items: int
    results: List[Dict[str, Any]]
    errors: List[APIError] = []
    processing_time: float


class FileAnalysis(BaseModel):
    """File analysis result model."""
    filename: str
    language: str
    size_bytes: int
    lines_count: int
    complexity_score: int
    issues_count: int
    last_modified: Optional[datetime] = None
    author: Optional[str] = None


class SecurityScanResult(BaseModel):
    """Security scan result model."""
    scan_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    vulnerabilities_found: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    scan_engine: str
    scan_version: str


class PerformanceReport(BaseModel):
    """Performance analysis report model."""
    analysis_id: str
    files_analyzed: int
    performance_issues: int
    optimization_suggestions: List[str]
    estimated_improvement: Optional[str] = None
    complexity_metrics: Dict[str, float]


class QualityReport(BaseModel):
    """Code quality report model."""
    analysis_id: str
    quality_score: float
    maintainability_index: float
    technical_debt_ratio: float
    code_smells: int
    test_coverage: Optional[float] = None
    documentation_coverage: Optional[float] = None


# WebSocket message models

class WebSocketMessage(BaseModel):
    """WebSocket message model."""
    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReviewUpdateMessage(WebSocketMessage):
    """Review update WebSocket message."""
    type: str = "review_update"
    review_id: str
    progress: ReviewProgress


class ErrorMessage(WebSocketMessage):
    """Error WebSocket message."""
    type: str = "error"
    error: APIError


# External API integration models

class GitHubRateLimit(BaseModel):
    """GitHub API rate limit model."""
    limit: int
    remaining: int
    reset: datetime
    used: int
    resource: str


class OpenAIUsage(BaseModel):
    """OpenAI API usage model."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: Optional[float] = None


class LangChainMetrics(BaseModel):
    """LangChain execution metrics."""
    chain_name: str
    execution_time: float
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_hit: bool = False
    model_name: str
    temperature: float