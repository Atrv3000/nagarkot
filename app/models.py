"""SQLAlchemy 2.0 domain models and schema definitions."""
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    type = Column(String(32), nullable=False)  # staff | client | system
    status = Column(String(32), nullable=False, default="active")  # active | absent
    client_id = Column(String(64), ForeignKey("clients.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    client = relationship("Client", back_populates="users")
    grants = relationship("Grant", back_populates="user", foreign_keys="[Grant.user_id]")


class Branch(Base):
    __tablename__ = "branches"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    code = Column(String(32), nullable=False, unique=True)


class Client(Base):
    __tablename__ = "clients"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)

    users = relationship("User", back_populates="client")


class Role(Base):
    """Roles are DATA, not code. Permissions belong to roles via versioned RolePermission."""
    __tablename__ = "roles"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    allowed_user_types = Column(String(128), nullable=False)  # e.g. "staff", "client", "system"
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class RolePermission(Base):
    """Versioned permission membership. Preserves historical role definitions."""
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(String(64), ForeignKey("roles.id"), nullable=False, index=True)
    permission = Column(String(64), nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    removed_at = Column(DateTime(timezone=True), nullable=True)

    role = relationship("Role", back_populates="permissions")


class Grant(Base):
    """Explicit grant of a role within an optional dimensional scope. Deny wins unconditionally."""
    __tablename__ = "grants"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    role_id = Column(String(64), ForeignKey("roles.id"), nullable=False)
    client_id = Column(String(64), ForeignKey("clients.id"), nullable=True)
    branch_id = Column(String(64), ForeignKey("branches.id"), nullable=True)
    direction = Column(String(32), nullable=True)  # IMPORT | EXPORT | NULL (all)
    mode = Column(String(32), nullable=True)       # AIR | FCL | LCL | NULL (all)
    effect = Column(String(16), nullable=False, default="allow")  # allow | deny
    valid_from = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    valid_to = Column(DateTime(timezone=True), nullable=True)
    granted_by = Column(String(64), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(String(64), ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=False)
    cover_for_user_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    batch_id = Column(String(64), nullable=False, index=True)

    user = relationship("User", back_populates="grants", foreign_keys=[user_id])
    role = relationship("Role")

    __table_args__ = (
        Index("idx_grants_user_revoked", "user_id", "revoked_at"),
    )


class Job(Base):
    """Shipment job lifecycle entity."""
    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True)
    ref = Column(String(64), unique=True, nullable=False, index=True)
    client_id = Column(String(64), ForeignKey("clients.id"), nullable=False)
    branch_id = Column(String(64), ForeignKey("branches.id"), nullable=False)
    direction = Column(String(32), nullable=False)  # IMPORT | EXPORT
    mode = Column(String(32), nullable=False)       # AIR | FCL | LCL
    stage = Column(String(32), nullable=False, default="CONFIRMED")  # CONFIRMED|PREPARED|CHECKED|FILED|CANCELLED|REOPENED
    assigned_to = Column(String(64), ForeignKey("users.id"), nullable=True)
    prepared_by = Column(String(64), ForeignKey("users.id"), nullable=True)
    checked_by = Column(String(64), ForeignKey("users.id"), nullable=True)
    filed_by = Column(String(64), ForeignKey("users.id"), nullable=True)
    cycle = Column(Integer, nullable=False, default=1)
    internal_notes = Column(Text, nullable=True)
    created_by = Column(String(64), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_jobs_scope_stage", "client_id", "branch_id", "direction", "mode", "stage"),
        Index("idx_jobs_stage_assigned", "stage", "assigned_to"),
        Index("idx_jobs_updated_id", "updated_at", "id"),
    )


class SoDRule(Base):
    """Separation of duties rules table."""
    __tablename__ = "sod_rules"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    action = Column(String(64), nullable=False)
    conflicting_field = Column(String(64), nullable=False)
    description = Column(Text, nullable=False)


class Approval(Base):
    """Two-person approval request for sensitive actions on filed/closed jobs."""
    __tablename__ = "approvals"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), ForeignKey("jobs.id"), nullable=False, index=True)
    action = Column(String(64), nullable=False)  # cancel_filed | reopen
    requested_by = Column(String(64), ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="pending")  # pending | approved | rejected | stale
    decided_by = Column(String(64), ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    """Append-only tamper-evident audit log enforced with SQLite triggers."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    actor_id = Column(String(64), nullable=False)
    actor_type = Column(String(32), nullable=False)  # staff | client | system
    actor_run_id = Column(String(64), nullable=True)  # parser batch run ID
    event_type = Column(String(64), nullable=False)
    job_id = Column(String(64), nullable=True)
    target_user_id = Column(String(64), nullable=True)
    action = Column(String(64), nullable=False)
    decision = Column(String(32), nullable=False)  # ALLOW | DENY | NEEDS_APPROVAL | EXECUTE
    reason_codes = Column(JSON, nullable=False, default=list)
    grant_ids_used = Column(JSON, nullable=False, default=list)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    is_override = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_audit_job_at", "job_id", "at"),
        Index("idx_audit_actor_at", "actor_id", "at"),
    )
