"""
SQLAlchemy 2.0 database models for AccessReaper v2.
Designed for SQLite with full compatibility for future PostgreSQL migration.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Identity(Base):
    __tablename__ = "identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    initials: Mapped[str] = mapped_column(String(10), nullable=False)
    job_role: Mapped[str] = mapped_column(String(100), nullable=False)
    team: Mapped[str] = mapped_column(String(100), nullable=False)
    employment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active, former, contractor
    current_project: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="identity", cascade="all, delete-orphan"
    )
    requests: Mapped[list["AccessRequest"]] = relationship(
        "AccessRequest", back_populates="identity", cascade="all, delete-orphan"
    )


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # GitHub, Firestore
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    project: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="resource", cascade="all, delete-orphan"
    )
    requests: Mapped[list["AccessRequest"]] = relationship(
        "AccessRequest", back_populates="resource", cascade="all, delete-orphan"
    )


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # FND-2841, etc.
    identity_id: Mapped[str] = mapped_column(String(36), ForeignKey("identities.id"), index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey("resources.id"), index=True, nullable=False)

    access_level: Mapped[str] = mapped_column(String(20), nullable=False)  # Admin, Write, Read, Editor, Viewer, None
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_active_text: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_risk: Mapped[str] = mapped_column(String(20), nullable=False)  # High, Medium, Low
    reason: Mapped[str] = mapped_column(String(255), nullable=False)

    direct_admin_bypass: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    privileged_inactive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    origin: Mapped[str] = mapped_column(String(20), default="sample", nullable=False)  # sample, github
    external_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # active, revoked_externally
    github_login: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    is_outside_collaborator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # JIT and Auto-reaper tracking fields
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    is_temporary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    warning_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    identity: Mapped["Identity"] = relationship("Identity", back_populates="assignments")
    resource: Mapped["Resource"] = relationship("Resource", back_populates="assignments")
    finding: Mapped[Optional["Finding"]] = relationship(
        "Finding",
        back_populates="assignment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # Matches assignment.id
    assignment_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("assignments.id"),
        unique=True,
        index=True,
        nullable=False,
    )
    original_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    original_severity: Mapped[str] = mapped_column(String(20), nullable=False)  # High, Medium, Low
    original_access: Mapped[str] = mapped_column(String(20), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # Open, Healthy, Remediated, Dismissed, Reviewed, Approved change
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    assignment: Mapped["Assignment"] = relationship("Assignment", back_populates="finding")


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # REQ-1042, etc.
    identity_id: Mapped[str] = mapped_column(String(36), ForeignKey("identities.id"), index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey("resources.id"), index=True, nullable=False)

    requested_access: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # Access request, Role change, Access removal
    business_reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[str] = mapped_column(String(20), nullable=False)  # High, Medium, Low
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Pending")  # Pending, Approved, Declined

    # JIT Duration
    duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_text: Mapped[str | None] = mapped_column(String(50), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    identity: Mapped["Identity"] = relationship("Identity", back_populates="requests")
    resource: Mapped["Resource"] = relationship("Resource", back_populates="requests")


class AuditRun(Base):
    __tablename__ = "audit_runs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # AUD-20261014-001
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Completed", nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # ["GitHub", "Firestore"]
    assignments: Mapped[int] = mapped_column(Integer, nullable=False)
    identities: Mapped[int] = mapped_column(Integer, nullable=False)
    high: Mapped[int] = mapped_column(Integer, nullable=False)
    medium: Mapped[int] = mapped_column(Integer, nullable=False)
    healthy: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved: Mapped[int] = mapped_column(Integer, nullable=False)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    sample: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="DRY_RUN", nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)  # manual, scheduled
    degraded_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditSnapshot(Base):
    __tablename__ = "audit_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    high: Mapped[int] = mapped_column(Integer, nullable=False)
    medium: Mapped[int] = mapped_column(Integer, nullable=False)
    healthy: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved: Mapped[int] = mapped_column(Integer, nullable=False)
    assignments: Mapped[int] = mapped_column(Integer, nullable=False)
    remediated: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # EVT-SEED-0, EVT-...
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    tag: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # Risk detected, Approved, Declined, Remediated, Dismissed, Audit, Request
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    assignment_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    audit_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    before: Mapped[str | None] = mapped_column(String(50), nullable=True)
    after: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tone: Mapped[str] = mapped_column(String(20), default="gray", nullable=False)
    icon: Mapped[str] = mapped_column(String(10), default="−", nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="DRY_RUN", nullable=False)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class RuleConfig(Base):
    __tablename__ = "rule_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="off", nullable=False)  # off, daily, weekly
    time_of_day: Mapped[str] = mapped_column(String(10), default="09:00", nullable=False)  # HH:MM
    day_of_week: Mapped[str | None] = mapped_column(String(20), nullable=True)  # mon, tue, wed, thu, fri, sat, sun
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    updated_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    pause_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class GitHubConfig(Base):
    __tablename__ = "github_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    org_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    encrypted_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_last4: Mapped[str | None] = mapped_column(String(10), nullable=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_before_audit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # SYNC-20261021-001
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # ok, partial, failed
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    repos_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    members_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    collaborators_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assignments_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assignments_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assignments_revoked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class GitHubIdentityMap(Base):
    __tablename__ = "github_identity_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="auto", nullable=False)  # auto, manual
    mapped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    mapped_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    account_type: Mapped[str] = mapped_column(String(20), default="user", nullable=False)  # user, bot, service, ignored
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SoDConflict(Base):
    __tablename__ = "sod_conflicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pattern_a: Mapped[str] = mapped_column(String(100), nullable=False)
    access_a: Mapped[str] = mapped_column(String(20), default="Admin", nullable=False)
    pattern_b: Mapped[str] = mapped_column(String(100), nullable=False)
    access_b: Mapped[str] = mapped_column(String(20), default="Admin", nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AIExplanation(Base):
    __tablename__ = "ai_explanations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"EXP-{uuid.uuid4().hex[:12]}")
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("audit_runs.id"), nullable=False, index=True)
    finding_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)  # success, fallback
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"NOTIF-{uuid.uuid4().hex[:12]}")
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)  # audit_completed, high_findings, approval_overdue, sync_degraded, audit_paused, user_pending_activation
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    admin_email: Mapped[str] = mapped_column(String(255), primary_key=True)
    email_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class EmailDigestSent(Base):
    __tablename__ = "email_digests_sent"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"DIGEST-{uuid.uuid4().hex[:12]}")
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    status: Mapped[str] = mapped_column(String(32), default="sent", nullable=False)
