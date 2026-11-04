"""Append-only audit logging infrastructure.

Protected at the database level by SQLite triggers preventing UPDATE and DELETE.
Logs:
- All job state transitions and overrides
- All grant creations and revocations (including DENIED attempts)
- All user status modifications
- All role and permission changes
- All denied mutating requests
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.clock import get_now
from app.models import AuditLog


def log_audit_event(
    db: Session,
    actor_id: str,
    actor_type: str,
    event_type: str,
    action: str,
    decision: str,
    actor_run_id: Optional[str] = None,
    job_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
    reason_codes: Optional[List[str]] = None,
    grant_ids_used: Optional[List[str]] = None,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    is_override: bool = False,
    at: Optional[datetime] = None,
) -> AuditLog:
    """Create and persist an append-only audit log record."""
    timestamp = at or get_now()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)

    entry = AuditLog(
        at=timestamp,
        actor_id=actor_id,
        actor_type=actor_type,
        actor_run_id=actor_run_id,
        event_type=event_type,
        job_id=job_id,
        target_user_id=target_user_id,
        action=action,
        decision=decision,
        reason_codes=reason_codes or [],
        grant_ids_used=grant_ids_used or [],
        before_state=before_state,
        after_state=after_state,
        is_override=is_override,
    )
    db.add(entry)
    db.flush()
    return entry
