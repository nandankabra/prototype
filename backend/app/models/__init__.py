"""Persisted evidence, processing runs, decisions and append-only audit records."""
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import String, Text, JSON, ForeignKey, DateTime, Integer, Float, Boolean, event
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Identity, Base):
    __tablename__ = 'users'
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(Text)


class Tender(Identity, Base):
    __tablename__ = 'tenders'
    reference: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(255))
    deadline: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    required_documents: Mapped[list] = mapped_column(JSON)
    local_content_threshold: Mapped[float] = mapped_column(Float, default=50)
    scoring_weights: Mapped[dict] = mapped_column(JSON)


class TenderRule(Identity, Base):
    __tablename__ = 'tender_rules'
    tender_id: Mapped[str] = mapped_column(ForeignKey('tenders.id'), index=True)
    rule_id: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(40))
    expression: Mapped[dict] = mapped_column(JSON)
    severity: Mapped[str] = mapped_column(String(20))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Bidder(Identity, Base):
    __tablename__ = 'bidders'
    name: Mapped[str] = mapped_column(String(255))
    pan: Mapped[str] = mapped_column(String(10))
    gstin: Mapped[str] = mapped_column(String(15))
    udyam: Mapped[str] = mapped_column(String(30))
    address: Mapped[str] = mapped_column(Text)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)


class Bid(Identity, Base):
    __tablename__ = 'bids'
    tender_id: Mapped[str] = mapped_column(ForeignKey('tenders.id'), index=True)
    bidder_id: Mapped[str] = mapped_column(ForeignKey('bidders.id'), index=True)
    scenario: Mapped[str] = mapped_column(String(40), default='CUSTOM')
    status: Mapped[str] = mapped_column(String(40), default='AWAITING_DOCUMENTS')
    current_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    final_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Document(Identity, Base):
    __tablename__ = 'documents'
    bid_id: Mapped[str] = mapped_column(ForeignKey('bids.id'), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(80))
    sha256: Mapped[str] = mapped_column(String(64))
    classification: Mapped[str] = mapped_column(String(50), default='miscellaneous')
    raw_text: Mapped[str] = mapped_column(Text, default='')
    normalized_text: Mapped[str] = mapped_column(Text, default='')
    pages: Mapped[list] = mapped_column(JSON, default=list)
    extraction: Mapped[dict] = mapped_column(JSON, default=dict)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)


class ProcessingRun(Identity, Base):
    __tablename__ = 'processing_runs'
    bid_id: Mapped[str] = mapped_column(ForeignKey('bids.id'), index=True)
    status: Mapped[str] = mapped_column(String(30), default='QUEUED')
    stages: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExtractedEntity(Identity, Base):
    __tablename__ = 'extracted_entities'
    run_id: Mapped[str] = mapped_column(ForeignKey('processing_runs.id'), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey('documents.id'), index=True)
    type: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(Text)
    normalized_value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    source_page: Mapped[int] = mapped_column(Integer)
    source_text: Mapped[str] = mapped_column(Text)
    bounding_box: Mapped[list] = mapped_column(JSON, default=list)


class SourceVerification(Identity, Base):
    __tablename__ = 'source_verifications'
    run_id: Mapped[str] = mapped_column(ForeignKey('processing_runs.id'), index=True)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey('extracted_entities.id'), nullable=True)
    source: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    identifier: Mapped[str] = mapped_column(Text)
    record: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    evidence: Mapped[dict] = mapped_column(JSON)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    checked_at: Mapped[str] = mapped_column(String(40))


class ComplianceResult(Identity, Base):
    __tablename__ = 'compliance_results'
    run_id: Mapped[str] = mapped_column(ForeignKey('processing_runs.id'), index=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey('tender_rules.id'))
    result: Mapped[dict] = mapped_column(JSON)


class RiskResult(Identity, Base):
    __tablename__ = 'risk_results'
    run_id: Mapped[str] = mapped_column(ForeignKey('processing_runs.id'), index=True)
    result: Mapped[dict] = mapped_column(JSON)


class AIRecommendation(Identity, Base):
    __tablename__ = 'ai_recommendations'
    run_id: Mapped[str] = mapped_column(ForeignKey('processing_runs.id'), index=True)
    result: Mapped[dict] = mapped_column(JSON)


class OfficerDecision(Identity, Base):
    __tablename__ = 'officer_decisions'
    bid_id: Mapped[str] = mapped_column(ForeignKey('bids.id'), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('processing_runs.id'))
    reviewer: Mapped[str] = mapped_column(String(255))
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    comments: Mapped[str] = mapped_column(Text, default='')
    ai_recommendation: Mapped[str] = mapped_column(String(60))
    is_override: Mapped[bool] = mapped_column(Boolean)


class AuditEvent(Identity, Base):
    __tablename__ = 'audit_events'
    sequence: Mapped[int] = mapped_column(Integer, unique=True)
    bid_id: Mapped[str | None] = mapped_column(ForeignKey('bids.id'), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(80))
    object_type: Mapped[str] = mapped_column(String(60))
    object_id: Mapped[str] = mapped_column(String(36))
    previous_state: Mapped[dict] = mapped_column(JSON, default=dict)
    new_state: Mapped[dict] = mapped_column(JSON, default=dict)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_hash: Mapped[str] = mapped_column(String(64))
    previous_hash: Mapped[str] = mapped_column(String(64))
    current_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)


@event.listens_for(AuditEvent, 'before_update')
@event.listens_for(AuditEvent, 'before_delete')
def reject_audit_mutation(*_):
    raise ValueError('Audit events are append-only')
