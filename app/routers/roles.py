"""Dynamic role management and versioned permission catalogue endpoints."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.clock import get_now
from app.db import get_db
from app.deps import get_current_user
from app.models import User, Role, RolePermission, Grant
from app.permissions import (
    ALL_PERMISSIONS,
    ROLES_MANAGE,
    ACCESS_MANAGE_PRIVILEGED,
    is_privileged_permission,
)
from app.audit import log_audit_event
from app.schemas import RoleResponse, RoleCreate, RolePermissionsUpdate

router = APIRouter(tags=["Roles & Privileges"])


def _caller_has_perm(db: Session, caller: User, perm: str) -> bool:
    """Check if caller currently holds an active grant for permission perm."""
    now = get_now()
    active_grants = (
        db.query(Grant)
        .join(
            RolePermission,
            and_(
                RolePermission.role_id == Grant.role_id,
                RolePermission.permission == perm,
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
    return active_grants is not None


@router.get("/roles", response_model=List[RoleResponse])
def list_roles(
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all roles and their current effective permissions."""
    now = get_now()
    roles = db.query(Role).all()
    results = []
    for r in roles:
        active_perms = [
            rp.permission
            for rp in db.query(RolePermission).filter(
                RolePermission.role_id == r.id,
                RolePermission.added_at <= now,
                or_(RolePermission.removed_at.is_(None), RolePermission.removed_at > now),
            ).all()
        ]
        results.append(
            RoleResponse(
                id=r.id,
                name=r.name,
                allowed_user_types=[t.strip() for t in r.allowed_user_types.split(",")],
                permissions=active_perms,
                created_at=r.created_at,
            )
        )
    return results


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    body: RoleCreate,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new role dynamically without software deployment (requires roles.manage)."""
    now = get_now()
    if not _caller_has_perm(db, caller, ROLES_MANAGE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: caller does not hold roles.manage",
        )

    existing = db.query(Role).filter(Role.id == body.id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Role '{body.id}' already exists")

    # Validate permissions exist in fixed catalogue
    unknown_perms = [p for p in body.permissions if p not in ALL_PERMISSIONS]
    if unknown_perms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown permissions: {unknown_perms}",
        )

    # Check if creating privileged role
    has_priv = any(is_privileged_permission(p) for p in body.permissions)
    if has_priv and not _caller_has_perm(db, caller, ACCESS_MANAGE_PRIVILEGED):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: creating a privileged role requires access.manage_privileged",
        )

    role = Role(
        id=body.id,
        name=body.name,
        allowed_user_types=",".join(body.allowed_user_types),
        created_at=now,
    )
    db.add(role)
    for p in body.permissions:
        db.add(RolePermission(role_id=role.id, permission=p, added_at=now))

    log_audit_event(
        db=db,
        actor_id=caller.id,
        actor_type=caller.type,
        event_type="ROLE_CHANGE",
        action="create_role",
        decision="EXECUTE",
        after_state={"role_id": role.id, "permissions": body.permissions},
    )
    db.commit()

    return RoleResponse(
        id=role.id,
        name=role.name,
        allowed_user_types=body.allowed_user_types,
        permissions=body.permissions,
        created_at=role.created_at,
    )


@router.put("/roles/{id}/permissions", response_model=RoleResponse)
def update_role_permissions(
    id: str,
    body: RolePermissionsUpdate,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update role permission membership. Maintains historical versioning (added_at, removed_at)."""
    now = get_now()
    if not _caller_has_perm(db, caller, ROLES_MANAGE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: caller does not hold roles.manage",
        )

    role = db.query(Role).filter(Role.id == id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{id}' not found")

    # Rule: Nobody may edit a role they currently hold a grant for!
    caller_holds_role = (
        db.query(Grant)
        .filter(
            Grant.user_id == caller.id,
            Grant.role_id == role.id,
            Grant.created_at <= now,
            Grant.valid_from <= now,
            or_(Grant.valid_to.is_(None), Grant.valid_to >= now),
            or_(Grant.revoked_at.is_(None), Grant.revoked_at > now),
        )
        .first()
    )
    if caller_holds_role:
        log_audit_event(
            db=db,
            actor_id=caller.id,
            actor_type=caller.type,
            event_type="ROLE_CHANGE",
            action="update_role_permissions",
            decision="DENY",
            reason_codes=["CANNOT_EDIT_OWN_ROLE"],
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Self-escalation violation: you cannot edit role '{role.id}' because you currently hold an active grant for it",
        )

    # Validate permissions exist in fixed catalogue
    unknown_perms = [p for p in body.permissions if p not in ALL_PERMISSIONS]
    if unknown_perms:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown permissions: {unknown_perms}")

    # Check privileged permissions
    current_active_rps = (
        db.query(RolePermission)
        .filter(
            RolePermission.role_id == role.id,
            RolePermission.added_at <= now,
            or_(RolePermission.removed_at.is_(None), RolePermission.removed_at > now),
        )
        .all()
    )
    current_perms = {rp.permission for rp in current_active_rps}
    target_perms = set(body.permissions)

    new_perms = target_perms - current_perms
    if any(is_privileged_permission(p) for p in new_perms):
        if not _caller_has_perm(db, caller, ACCESS_MANAGE_PRIVILEGED):
            log_audit_event(
                db=db,
                actor_id=caller.id,
                actor_type=caller.type,
                event_type="ROLE_CHANGE",
                action="update_role_permissions",
                decision="DENY",
                reason_codes=["PRIVILEGED_PERMISSIONS_REQUIRE_MANAGE_PRIVILEGED"],
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Adding privileged permissions to a role requires access.manage_privileged",
            )

    # Versioning: soft-delete removed permissions with removed_at = now
    removed_perms = current_perms - target_perms
    for rp in current_active_rps:
        if rp.permission in removed_perms:
            rp.removed_at = now

    # Add newly granted permissions
    for p in new_perms:
        db.add(RolePermission(role_id=role.id, permission=p, added_at=now))

    log_audit_event(
        db=db,
        actor_id=caller.id,
        actor_type=caller.type,
        event_type="ROLE_CHANGE",
        action="update_role_permissions",
        decision="EXECUTE",
        before_state={"permissions": list(current_perms)},
        after_state={"permissions": list(target_perms), "reason": body.reason},
    )
    db.commit()

    return RoleResponse(
        id=role.id,
        name=role.name,
        allowed_user_types=[t.strip() for t in role.allowed_user_types.split(",")],
        permissions=list(target_perms),
        created_at=role.created_at,
    )
