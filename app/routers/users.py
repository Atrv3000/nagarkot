"""User status management and absence handover endpoints."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.clock import get_now
from app.db import get_db
from app.deps import get_current_user
from app.models import User, Grant, RolePermission
from app.permissions import ACCESS_MANAGE
from app.grants import auto_unassign_ineligible_jobs
from app.audit import log_audit_event
from app.schemas import UserResponse, UserStatusUpdate

router = APIRouter(tags=["User Administration"])


def _caller_can_manage_users(db: Session, caller: User) -> bool:
    """Verify caller has active access.manage permission."""
    now = get_now()
    active = (
        db.query(Grant)
        .join(
            RolePermission,
            and_(
                RolePermission.role_id == Grant.role_id,
                RolePermission.permission == ACCESS_MANAGE,
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


@router.patch("/users/{id}/status", response_model=UserResponse)
def update_user_status(
    id: str,
    body: UserStatusUpdate,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a user active or absent. Automatically unassigns in-flight jobs when marked absent."""
    now = get_now()
    if not _caller_can_manage_users(db, caller):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: caller does not hold active access.manage permission",
        )

    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{id}' not found")

    old_status = user.status
    user.status = body.status

    log_audit_event(
        db=db,
        actor_id=caller.id,
        actor_type=caller.type,
        event_type="USER_STATUS_CHANGE",
        action="update_status",
        decision="EXECUTE",
        target_user_id=user.id,
        before_state={"status": old_status},
        after_state={"status": user.status, "reason": body.reason},
    )

    # When marked absent, automatically return in-flight jobs to pool
    if body.status == "absent":
        auto_unassign_ineligible_jobs(db, user, actor_id=caller.id, actor_type=caller.type)

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
