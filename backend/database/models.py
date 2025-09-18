"""SQLAlchemy database models."""

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import TypeDecorator, CHAR
import uuid
import json

from .connection import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses CHAR(36), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value


class JSONString(TypeDecorator):
    """JSON type that stores data as text/string."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return value


class Review(Base):
    """Review model for storing code review data."""
    __tablename__ = "reviews"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    type = Column(String(50), nullable=False)  # manual, pr_webhook, scheduled
    status = Column(String(50), nullable=False, default="pending")  # pending, in_progress, completed, failed

    # Repository information
    repository = Column(String(255), nullable=True, index=True)
    pr_number = Column(Integer, nullable=True, index=True)
    commit_sha = Column(String(40), nullable=True)

    # Review configuration (JSON serialized)
    configuration = Column(JSONString, nullable=False, default=dict)

    # Review results
    overall_score = Column(Float, nullable=False, default=0.0)
    total_issues = Column(Integer, nullable=False, default=0)
    security_issues_count = Column(Integer, nullable=False, default=0)
    performance_issues_count = Column(Integer, nullable=False, default=0)
    quality_issues_count = Column(Integer, nullable=False, default=0)

    # Metrics (JSON serialized)
    metrics = Column(JSONString, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # User/Creator information
    created_by = Column(String(255), nullable=True)

    # Processing information
    processing_time = Column(Float, nullable=True)  # seconds
    ai_model_used = Column(String(100), nullable=True)
    ai_tokens_used = Column(Integer, nullable=True)
    ai_cost = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)

    # GitHub integration
    github_check_run_id = Column(Integer, nullable=True)
    github_status_context = Column(String(255), default="git-review-assistant")
    comments_posted = Column(Integer, nullable=False, default=0)

    # Relationships
    issues = relationship("ReviewIssue", back_populates="review", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Review(id={self.id}, repository={self.repository}, status={self.status})>"


class ReviewIssue(Base):
    """Review issue model for storing individual issues found during review."""
    __tablename__ = "review_issues"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    review_id = Column(GUID(), ForeignKey("reviews.id"), nullable=False, index=True)

    # Issue classification
    category = Column(String(50), nullable=False, index=True)  # security, performance, quality, style
    severity = Column(String(20), nullable=False, index=True)  # critical, high, medium, low, info

    # Issue details
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    # Location information
    file_path = Column(String(512), nullable=True)
    line_number = Column(Integer, nullable=True)
    column_number = Column(Integer, nullable=True)

    # Code context
    code_snippet = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)

    # Rule/Tool information
    rule_id = Column(String(100), nullable=True)
    tool_name = Column(String(100), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confidence_score = Column(Float, nullable=True)  # AI confidence in issue

    # GitHub integration
    github_comment_id = Column(Integer, nullable=True)
    github_comment_url = Column(String(512), nullable=True)

    # Relationships
    review = relationship("Review", back_populates="issues")

    def __repr__(self):
        return f"<ReviewIssue(id={self.id}, category={self.category}, severity={self.severity})>"


class WebhookDelivery(Base):
    """Webhook delivery tracking model."""
    __tablename__ = "webhook_deliveries"

    id = Column(String(100), primary_key=True)  # GitHub delivery ID + timestamp
    event_type = Column(String(50), nullable=False, index=True)
    delivery_id = Column(String(100), nullable=False, index=True)

    # Processing status
    status = Column(String(50), nullable=False, default="pending")  # pending, processing, completed, failed

    # Timestamps
    received_at = Column(DateTime(timezone=True), nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Repository information
    repository = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=True, index=True)

    # Processing results
    review_id = Column(GUID(), ForeignKey("reviews.id"), nullable=True)
    error_message = Column(Text, nullable=True)
    processing_time = Column(Float, nullable=True)

    # Payload information (metadata only, not full payload for privacy)
    payload_size = Column(Integer, nullable=True)
    sender = Column(String(255), nullable=True)
    installation_id = Column(Integer, nullable=True)

    # Relationships
    review = relationship("Review")

    def __repr__(self):
        return f"<WebhookDelivery(id={self.id}, event_type={self.event_type}, status={self.status})>"


class User(Base):
    """User model for authentication and tracking."""
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=True, unique=True, index=True)
    name = Column(String(255), nullable=True)

    # GitHub integration
    github_id = Column(Integer, nullable=True, unique=True, index=True)
    github_username = Column(String(255), nullable=True, unique=True, index=True)
    avatar_url = Column(String(512), nullable=True)

    # Authentication
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # API usage tracking
    api_calls_count = Column(Integer, nullable=False, default=0)
    last_api_call = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"


class ApiKey(Base):
    """API key model for authentication."""
    __tablename__ = "api_keys"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)  # Hashed API key

    # Permissions
    scopes = Column(JSONString, nullable=False, default=list)  # List of allowed scopes
    is_active = Column(Boolean, default=True, nullable=False)

    # Usage tracking
    last_used = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<ApiKey(id={self.id}, name={self.name})>"


class ReviewTemplate(Base):
    """Review template model for customizable review configurations."""
    __tablename__ = "review_templates"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Template configuration
    configuration = Column(JSONString, nullable=False)  # Review settings
    prompts = Column(JSONString, nullable=True)  # Custom AI prompts
    rules = Column(JSONString, nullable=True)  # Custom rules

    # Ownership
    created_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)

    # Usage statistics
    usage_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    creator = relationship("User")

    def __repr__(self):
        return f"<ReviewTemplate(id={self.id}, name={self.name})>"


class AuditLog(Base):
    """Audit log model for tracking system events."""
    __tablename__ = "audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Event information
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSONString, nullable=True)

    # User information
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    user_ip = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(512), nullable=True)

    # Resource information
    resource_type = Column(String(100), nullable=True, index=True)
    resource_id = Column(String(255), nullable=True, index=True)

    # Result
    success = Column(Boolean, nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, event_type={self.event_type})>"


# Create table references for easier imports
review_table = Review.__table__
review_issue_table = ReviewIssue.__table__
webhook_delivery_table = WebhookDelivery.__table__
user_table = User.__table__
api_key_table = ApiKey.__table__
review_template_table = ReviewTemplate.__table__
audit_log_table = AuditLog.__table__