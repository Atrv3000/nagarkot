"""Grant administration endpoints."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db import get_db
from app.deps import get_current_user
from app.models import User, Grant
from app.grants import create_grants, revoke_grant, describe_user_access
from app.schemas import (
    GrantCreateRequest,
    GrantRevokeRequest,
    GrantResponse,
    UserAccessSummary,
)

router = APIRouter(tags=["Access & Grants"])


@router.post("/grants", response_model=List[GrantResponse], status_code=status.HTTP_201_CREATED)
def grant_roles(
    body: GrantCreateRequest,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grant roles to a user. Supports multi-scope expansion within one transaction."""
    grants = create_grants(db, grantor=caller, target_user_id=body.user_id, items=body.grants)
    return [GrantResponse.model_validate(g) for g in grants]


@router.post("/grants/{id}/revoke", response_model=GrantResponse)
def revoke_role_grant(
    id: str,
    body: GrantRevokeRequest,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a grant, check super admin lock-out guard, and auto-unassign in-flight jobs."""
    grant = revoke_grant(db, grantor=caller, grant_id=id, reason=body.reason)
    return GrantResponse.model_validate(grant)


@router.get("/users/{id}/grants", response_model=List[GrantResponse])
def get_user_grants(
    id: str,
    at: Optional[str] = Query(None, description="Optional historical ISO timestamp"),
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List active grants for a user as of timestamp `at`."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{id}' not found")

    eval_time = None
    if at:
        eval_time = datetime.fromisoformat(at)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)
    else:
        from app.clock import get_now
        eval_time = get_now()

    grants = (
        db.query(Grant)
        .filter(
            Grant.user_id == id,
            Grant.created_at <= eval_time,
            Grant.valid_from <= eval_time,
            or_(Grant.valid_to.is_(None), Grant.valid_to >= eval_time),
            or_(Grant.revoked_at.is_(None), Grant.revoked_at > eval_time),
        )
        .all()
    )
    return [GrantResponse.model_validate(g) for g in grants]


@router.get("/users/{id}/access", response_model=UserAccessSummary)
def get_user_access_summary(
    id: str,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Plain-English summary of what a person can do and where their grants apply."""
    return describe_user_access(db, user_id=id)
