"""Grant management, multi-scope expansion, scope containment, and auto-unassignment."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException, status

from app.clock import get_now
from app.models import (
    User,
    Role,
    RolePermission,
    Grant,
    Job,
)
from app.permissions import (
    ACCESS_MANAGE,
    ACCESS_MANAGE_PRIVILEGED,
    is_privileged_role,
)
from app.audit import log_audit_event
from app.schemas import GrantCreateItem, GrantResponse, UserAccessSummary


def _check_scope_contained(grantor_grant: Grant, item: GrantCreateItem) -> bool:
    """Verify if grantor's grant scope contains the child grant's scope.
    A non-NULL field in grantor's scope requires the child scope to specify the exact same value.
    """
    if grantor_grant.client_id is not None:
        if item.client_id is None or item.client_id != grantor_grant.client_id:
            return False
    if grantor_grant.branch_id is not None:
        if item.branch_id is None or item.branch_id != grantor_grant.branch_id:
            return False
    if grantor_grant.direction is not None:
        if item.direction is None or item.direction != grantor_grant.direction:
            return False
    if grantor_grant.mode is not None:
        if item.mode is None or item.mode != grantor_grant.mode:
            return False
    return True


def auto_unassign_ineligible_jobs(
    db: Session,
    target_user: User,
    actor_id: str,
    actor_type: str,
) -> List[str]:
    """Inspect all in-flight jobs assigned to target_user.
    If the user can no longer perform the next action, unassign and return to pool.
    """
    from app.decision import decide

    now = get_now()
    in_flight_stages = ["CONFIRMED", "PREPARED", "CHECKED", "REOPENED"]
    assigned_jobs = (
        db.query(Job)
        .filter(
            Job.assigned_to == target_user.id,
            Job.stage.in_(in_flight_stages),
        )
        .all()
    )

    unassigned_ids = []
    for job in assigned_jobs:
        # Determine next action
        if job.stage in ("CONFIRMED", "REOPENED"):
            next_action = "prepare"
        elif job.stage == "PREPARED":
            next_action = "check"
        elif job.stage == "CHECKED":
            next_action = "file"
        else:
            continue

        dec = decide(db, user_id=target_user.id, action=next_action, job=job, at=now)
        if not dec.allowed:
            before = {"assigned_to": target_user.id, "stage": job.stage}
            job.assigned_to = None
            job.updated_at = now
            after = {"assigned_to": None, "stage": job.stage}

            log_audit_event(
                db=db,
                actor_id=actor_id,
                actor_type=actor_type,
                event_type="AUTO_UNASSIGNED",
                action="auto_unassign",
                decision="EXECUTE",
                job_id=job.id,
                target_user_id=target_user.id,
                reason_codes=["ROLE_OR_STATUS_CHANGED", dec.primary_reason or "INELIGIBLE"],
                before_state=before,
                after_state=after,
            )
            unassigned_ids.append(job.id)

    db.flush()
    return unassigned_ids


def create_grants(
    db: Session,
    grantor: User,
    target_user_id: str,
    items: List[GrantCreateItem],
) -> List[Grant]:
    """Expand and persist a batch of grants with full authorization checks."""
    now = get_now()

    # Rule 1: Nobody can create a grant for themselves
    if grantor.id == target_user_id:
        log_audit_event(
            db=db,
            actor_id=grantor.id,
            actor_type=grantor.type,
            event_type="GRANT_CREATE",
            action="create_grant",
            decision="DENY",
            target_user_id=target_user_id,
            reason_codes=["SELF_GRANT_PROHIBITED"],
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-escalation violation: users cannot grant roles to themselves",
        )

    target_user = db.query(User).filter(User.id == target_user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target user '{target_user_id}' not found")

    # Fetch grantor's active access.manage grants
    grantor_access_grants = (
        db.query(Grant)
        .join(
            RolePermission,
            and_(
                RolePermission.role_id == Grant.role_id,
                RolePermission.permission.in_([ACCESS_MANAGE, ACCESS_MANAGE_PRIVILEGED]),
                RolePermission.added_at <= now,
                or_(RolePermission.removed_at.is_(None), RolePermission.removed_at > now),
            ),
        )
        .filter(
            Grant.user_id == grantor.id,
            Grant.effect == "allow",
            Grant.created_at <= now,
            Grant.valid_from <= now,
            or_(Grant.valid_to.is_(None), Grant.valid_to >= now),
            or_(Grant.revoked_at.is_(None), Grant.revoked_at > now),
        )
        .all()
    )

    if not grantor_access_grants:
        log_audit_event(
            db=db,
            actor_id=grantor.id,
            actor_type=grantor.type,
            event_type="GRANT_CREATE",
            action="create_grant",
            decision="DENY",
            target_user_id=target_user_id,
            reason_codes=["NO_ACCESS_MANAGE_PERMISSION"],
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Grantor does not hold active access.manage permission",
        )

    # Has privileged grant power?
    has_privileged_access = any(
        db.query(RolePermission)
        .filter(
            RolePermission.role_id == g.role_id,
            RolePermission.permission == ACCESS_MANAGE_PRIVILEGED,
            RolePermission.added_at <= now,
            or_(RolePermission.removed_at.is_(None), RolePermission.removed_at > now),
        )
        .first()
        for g in grantor_access_grants
    )

    batch_id = f"BATCH-{uuid.uuid4().hex[:8]}"
    created_grants: List[Grant] = []

    for item in items:
        role = db.query(Role).filter(Role.id == item.role_id).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{item.role_id}' not found")

        # Get role permissions
        role_perms = [
            rp.permission
            for rp in db.query(RolePermission).filter(
                RolePermission.role_id == role.id,
                RolePermission.added_at <= now,
                or_(RolePermission.removed_at.is_(None), RolePermission.removed_at > now),
            ).all()
        ]

        role_is_priv = is_privileged_role(role_perms)
        if role_is_priv and not has_privileged_access:
            log_audit_event(
                db=db,
                actor_id=grantor.id,
                actor_type=grantor.type,
                event_type="GRANT_CREATE",
                action="create_grant",
                decision="DENY",
                target_user_id=target_user_id,
                reason_codes=["PRIVILEGED_ROLE_REQUIRES_MANAGE_PRIVILEGED"],
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role.id}' is privileged; granting requires access.manage_privileged",
            )

        # Check scope containment
        contained = False
        for g in grantor_access_grants:
            # If role is privileged, containing grant must also hold access.manage_privileged
            if role_is_priv:
                has_priv = db.query(RolePermission).filter(
                    RolePermission.role_id == g.role_id,
                    RolePermission.permission == ACCESS_MANAGE_PRIVILEGED,
                ).first()
                if not has_priv:
                    continue

            if _check_scope_contained(g, item):
                contained = True
                break

        if not contained:
            log_audit_event(
                db=db,
                actor_id=grantor.id,
                actor_type=grantor.type,
                event_type="GRANT_CREATE",
                action="create_grant",
                decision="DENY",
                target_user_id=target_user_id,
                reason_codes=["SCOPE_CONTAINMENT_VIOLATION"],
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Grantor scope does not contain the requested grant scope",
            )

        # Check role-type compatibility
        allowed_types = [t.strip() for t in role.allowed_user_types.split(",")]
        if target_user.type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{role.id}' allows types {allowed_types}, but user '{target_user.id}' is '{target_user.type}'",
            )

        if target_user.type == "client":
            if item.client_id != target_user.client_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Client users can only be granted roles for their assigned client '{target_user.client_id}'",
                )

        # Build grant record
        valid_from = item.valid_from or now
        grant_id = f"GRT-{uuid.uuid4().hex[:10]}"
        g_row = Grant(
            id=grant_id,
            user_id=target_user_id,
            role_id=role.id,
            client_id=item.client_id,
            branch_id=item.branch_id,
            direction=item.direction,
            mode=item.mode,
            effect=item.effect,
            valid_from=valid_from,
            valid_to=item.valid_to,
            granted_by=grantor.id,
            created_at=now,
            reason=item.reason,
            cover_for_user_id=item.cover_for_user_id,
            batch_id=batch_id,
        )
        db.add(g_row)
        created_grants.append(g_row)

    db.flush()

    # Audit all created grants
    for g_row in created_grants:
        log_audit_event(
            db=db,
            actor_id=grantor.id,
            actor_type=grantor.type,
            event_type="GRANT_CREATE",
            action="create_grant",
            decision="ALLOW",
            target_user_id=target_user_id,
            grant_ids_used=[g_row.id],
            after_state={
                "id": g_row.id,
                "role_id": g_row.role_id,
                "scope": f"client={g_row.client_id}, branch={g_row.branch_id}, dir={g_row.direction}, mode={g_row.mode}",
                "effect": g_row.effect,
            },
        )

    db.commit()
    return created_grants


def revoke_grant(
    db: Session,
    grantor: User,
    grant_id: str,
    reason: str,
) -> Grant:
    """Revoke a grant, check last super admin guard, and auto-unassign now-ineligible jobs."""
    now = get_now()
    grant = db.query(Grant).filter(Grant.id == grant_id).first()
    if not grant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Grant '{grant_id}' not found")

    if grant.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Grant is already revoked")

    # Rule 1: Nobody can revoke a grant for themselves
    if grantor.id == grant.user_id:
        log_audit_event(
            db=db,
            actor_id=grantor.id,
            actor_type=grantor.type,
            event_type="GRANT_REVOKE",
            action="revoke_grant",
            decision="DENY",
            target_user_id=grant.user_id,
            reason_codes=["SELF_REVOCATION_PROHIBITED"],
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-escalation violation: users cannot revoke their own grants",
        )

    # Rule 6: Lock-out guard: Cannot revoke the last active Super Admin grant
    if grant.role_id == "super_admin":
        active_super_admins = (
            db.query(Grant)
            .filter(
                Grant.role_id == "super_admin",
                Grant.effect == "allow",
                Grant.revoked_at.is_(None),
                Grant.valid_from <= now,
                or_(Grant.valid_to.is_(None), Grant.valid_to >= now),
            )
            .count()
        )
        if active_super_admins <= 1:
            log_audit_event(
                db=db,
                actor_id=grantor.id,
                actor_type=grantor.type,
                event_type="GRANT_REVOKE",
                action="revoke_grant",
                decision="DENY",
                target_user_id=grant.user_id,
                reason_codes=["LAST_SUPER_ADMIN_GUARD"],
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lock-out guard: cannot revoke the last active Super Admin grant",
            )

    # Perform revocation
    grant.revoked_at = now
    grant.revoked_by = grantor.id
    grant.reason = f"{grant.reason} [Revocation reason: {reason}]"

    log_audit_event(
        db=db,
        actor_id=grantor.id,
        actor_type=grantor.type,
        event_type="GRANT_REVOKE",
        action="revoke_grant",
        decision="ALLOW",
        target_user_id=grant.user_id,
        grant_ids_used=[grant.id],
        after_state={"id": grant.id, "revoked_at": now.isoformat(), "revoked_by": grantor.id},
    )

    # Rule 8: Auto-unassign in-flight jobs that user can no longer act on
    target_user = db.query(User).filter(User.id == grant.user_id).first()
    if target_user:
        auto_unassign_ineligible_jobs(db, target_user, actor_id=grantor.id, actor_type=grantor.type)

    db.commit()
    db.refresh(grant)
    return grant


def describe_user_access(db: Session, user_id: str, at: Optional[datetime] = None) -> UserAccessSummary:
    """Provide a comprehensive plain-English breakdown of all active grants and capabilities."""
    now = at or get_now()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")

    active_grants = (
        db.query(Grant)
        .filter(
            Grant.user_id == user.id,
            Grant.created_at <= now,
            Grant.valid_from <= now,
            or_(Grant.valid_to.is_(None), Grant.valid_to >= now),
            or_(Grant.revoked_at.is_(None), Grant.revoked_at > now),
        )
        .all()
    )

    rules = []
    if user.status == "absent":
        rules.append("User is currently marked ABSENT: all active operational permissions suspended (view retained)")

    for g in active_grants:
        effect_str = "ALLOW" if g.effect == "allow" else "DENY"
        scope_parts = []
        scope_parts.append(f"Client: {g.client_id or 'ALL'}")
        scope_parts.append(f"Branch: {g.branch_id or 'ALL'}")
        scope_parts.append(f"Direction: {g.direction or 'ALL'}")
        scope_parts.append(f"Mode: {g.mode or 'ALL'}")
        scope_desc = ", ".join(scope_parts)

        cover_desc = f" (Absence cover for {g.cover_for_user_id})" if g.cover_for_user_id else ""
        expiry_desc = f" (Expires: {g.valid_to.isoformat()})" if g.valid_to else ""
        rules.append(f"[{effect_str}] Role: '{g.role_id}' on ({scope_desc}){cover_desc}{expiry_desc}")

    return UserAccessSummary(
        user_id=user.id,
        name=user.name,
        status=user.status,
        user_type=user.type,
        active_grants_count=len(active_grants),
        plain_english_rules=rules,
    )
