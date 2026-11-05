"""Common API dependencies: database sessions and caller authentication."""
from typing import Optional
from fastapi import Header, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id", description="User ID identifying caller"),
    db: Session = Depends(get_db),
) -> User:
    """Resolve caller user model from X-User-Id header."""
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header 'X-User-Id' is required for authentication",
        )
    user = db.query(User).filter(User.id == x_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User '{x_user_id}' not found in directory",
        )
    return user


def get_actor_run_id(
    x_run_id: Optional[str] = Header(None, alias="X-Run-Id", description="Batch run ID for system actors"),
) -> Optional[str]:
    """Extract optional parser batch run ID."""
    return x_run_id


def caller_has_access_or_audit(db: Session, caller: User) -> bool:
    """Verify if caller holds active access.manage, access.manage_privileged, or audit.view."""
    from app.clock import get_now
    from app.models import Grant, RolePermission
    from app.permissions import ACCESS_MANAGE, ACCESS_MANAGE_PRIVILEGED, AUDIT_VIEW
    from sqlalchemy import and_, or_

    now = get_now()
    active = (
        db.query(Grant)
        .join(
            RolePermission,
            and_(
                RolePermission.role_id == Grant.role_id,
                RolePermission.permission.in_([ACCESS_MANAGE, ACCESS_MANAGE_PRIVILEGED, AUDIT_VIEW]),
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
