"""SQLAlchemy models. Three tables: reviews, findings, webhook_deliveries.

Model output is stored (title, evidence, recommendation) so the dashboard can
show what was posted; patches are never stored. The evidence column holds a
quoted line from a diff that has already been through redaction."""

import json
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator

from .connection import Base


def _uuid() -> str:
    return str(uuid.uuid4())


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
    delivery_id = Column(String(100), nullable=True)

    files_total = Column(Integer, nullable=False, default=0)
    files_reviewed = Column(Integer, nullable=False, default=0)
    files_skipped = Column(Integer, nullable=False, default=0)
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

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    review = relationship("Review", back_populates="findings")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    delivery_id = Column(String(100), primary_key=True)
    event = Column(String(50), nullable=False)
    action = Column(String(50), nullable=True)
    repository = Column(String(255), nullable=True, index=True)
    pr_number = Column(Integer, nullable=True)
    head_sha = Column(String(40), nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="received")  # received, queued, running, completed, failed
    review_id = Column(String(36), nullable=True)
