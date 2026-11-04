"""Audit trail query endpoint."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.clock import get_now
from app.db import get_db
from app.deps import get_current_user
from app.models import User, Grant, RolePermission, AuditLog
from app.permissions import AUDIT_VIEW
from app.schemas import AuditLogResponse

router = APIRouter(tags=["Audit & Compliance"])


def _caller_can_view_audit(db: Session, caller: User) -> bool:
    """Verify caller holds active audit.view permission."""
    now = get_now()
    active = (
        db.query(Grant)
        .join(
            RolePermission,
            and_(
                RolePermission.role_id == Grant.role_id,
                RolePermission.permission == AUDIT_VIEW,
                RolePermission.added_at <= now,
                or_(RolePermission.removed_at.is_(None), RolePermission.removed_at > now),
            ),
        )
        .filter(
            Grant.user_id == caller.id,
            Grant.effect == "allow",
            Grant.created_at <= now,
            Grant.valid_from <= now,
            or_(Grant.valid_to.is_(None), Grant.valid_to >= now),
            or_(Grant.revoked_at.is_(None), Grant.revoked_at > now),
        )
        .first()
    )
    return active is not None


@router.get("/audit", response_model=List[AuditLogResponse])
def query_audit_trail(
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    actor_id: Optional[str] = Query(None, description="Filter by actor user ID"),
    target_user_id: Optional[str] = Query(None, description="Filter by target user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    from_at: Optional[str] = Query(None, description="ISO timestamp start range"),
    to_at: Optional[str] = Query(None, description="ISO timestamp end range"),
    limit: int = Query(50, ge=1, le=500, description="Max entries to return"),
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Query immutable audit records (requires audit.view permission)."""
    if not _caller_can_view_audit(db, caller):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: caller does not hold audit.view permission",
        )

    query = db.query(AuditLog)
    if job_id:
        query = query.filter(AuditLog.job_id == job_id)
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    if target_user_id:
        query = query.filter(AuditLog.target_user_id == target_user_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if from_at:
        dt_from = datetime.fromisoformat(from_at)
        if dt_from.tzinfo is None:
            dt_from = dt_from.replace(tzinfo=timezone.utc)
        query = query.filter(AuditLog.at >= dt_from)
    if to_at:
        dt_to = datetime.fromisoformat(to_at)
        if dt_to.tzinfo is None:
            dt_to = dt_to.replace(tzinfo=timezone.utc)
        query = query.filter(AuditLog.at <= dt_to)

    results = query.order_by(AuditLog.at.desc(), AuditLog.id.desc()).limit(limit).all()
    return results
