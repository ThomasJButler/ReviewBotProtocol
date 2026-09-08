"""SQLAlchemy models. Three tables: reviews, findings, webhook_deliveries.

Model output is stored (title, evidence, recommendation) so the dashboard can
show what was posted; patches are never stored. The evidence column holds a
quoted line from a diff that has already been through redaction."""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator

from .connection import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JSONString(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else json.dumps(value)

    def process_result_value(self, value, dialect):
        return None if value is None else json.loads(value)


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String(36), primary_key=True, default=_uuid)
    repository = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False, index=True)
    pr_title = Column(String(255), nullable=True)
    head_sha = Column(String(40), nullable=True)
    is_fork = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="running", index=True)  # running, completed, failed
    model = Column(String(100), nullable=True)
    cross_model = Column(String(100), nullable=True)
    cross_added = Column(Integer, nullable=False, default=0)
    cross_refuted = Column(Integer, nullable=False, default=0)
    delivery_id = Column(String(100), nullable=True)

    files_total = Column(Integer, nullable=False, default=0)
    files_reviewed = Column(Integer, nullable=False, default=0)
    files_skipped = Column(Integer, nullable=False, default=0)
    # where a running review is up to: phase review, cross-examine or done; files finished of total;
    # the file the model is on. Updated once per file by the runner, shown by the dashboard.
    progress_phase = Column(String(20), nullable=True)
    progress_done = Column(Integer, nullable=False, default=0)
    progress_total = Column(Integer, nullable=False, default=0)
    progress_file = Column(String(512), nullable=True)
    skipped = Column(JSONString, nullable=True)
    findings_count = Column(Integer, nullable=False, default=0)
    severity_counts = Column(JSONString, nullable=True)
    findings_dropped = Column(Integer, nullable=False, default=0)
    redactions = Column(Integer, nullable=False, default=0)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    comment_url = Column(String(512), nullable=True)
    summary = Column(Text, nullable=True)
    useful = Column(Boolean, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    findings = relationship("Finding", back_populates="review", cascade="all, delete-orphan", order_by="Finding.line")


class Finding(Base):
    __tablename__ = "findings"

    id = Column(String(36), primary_key=True, default=_uuid)
    review_id = Column(String(36), ForeignKey("reviews.id"), nullable=False, index=True)
    path = Column(String(512), nullable=False)
    line = Column(Integer, nullable=False)
    category = Column(String(20), nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    evidence = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    source_model = Column(String(100), nullable=True)   # which model raised it
    cross_verdict = Column(String(20), nullable=True)   # real, false_positive, or NULL when not examined
    cross_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    review = relationship("Review", back_populates="findings")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    # The replay check reads the hash and then inserts; the unique index makes the
    # race between those two a constraint. record() already answers the loser's
    # IntegrityError with False, which the webhook handler reports as "duplicate".
    # An existing database gets the index from add_missing_indexes at startup.
    __table_args__ = (Index("ix_webhook_deliveries_body_sha256_unique", "body_sha256", unique=True),)

    delivery_id = Column(String(100), primary_key=True)
    event = Column(String(50), nullable=False)
    action = Column(String(50), nullable=True)
    repository = Column(String(255), nullable=True, index=True)
    pr_number = Column(Integer, nullable=True)
    head_sha = Column(String(40), nullable=True)
    body_sha256 = Column(String(64), nullable=True)  # what the signature actually covers; unique, see __table_args__
    received_at = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="received")  # received, queued, running, completed, failed
    review_id = Column(String(36), nullable=True)
