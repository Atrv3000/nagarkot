"""Core decision engine for Nagarkot Access Control Service.

Implements the deterministic 8-stage decision pipeline:
1. USER_KNOWN (and user type compatibility)
2. USER_ACTIVE (absence check; absent users retain view, cannot act)
3. JOB_DATA_COMPLETE (shipment attributes valid)
4. ACTION_KNOWN (action in permission catalogue)
5. STAGE_VALID (workflow state transition validation)
6. GRANT_COVERS_SCOPE (temporal grants, deny-precedence, dimensional scope)
7. SOD_OK (Separation of duties: maker != checker, requester != approver)
8. REASON_PROVIDED (mandatory for override and sensitive actions)
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.clock import get_now
from app.models import (
    User,
    Job,
    Grant,
    RolePermission,
    AuditLog,
)
from app.permissions import (
    ACTION_TO_PERMISSION,
    JOB_VIEW,
)
from app.schemas import CheckDetail, DecisionResponse

logger = logging.getLogger(__name__)

# Valid stages and dimensions
VALID_STAGES = {"CONFIRMED", "PREPARED", "CHECKED", "FILED", "CANCELLED", "REOPENED"}
VALID_DIRECTIONS = {"IMPORT", "EXPORT"}
VALID_MODES = {"AIR", "FCL", "LCL"}


def _reconstruct_user_status_at(db: Session, user: User, at: datetime) -> str:
    """Reconstruct a user's status at historical time `at` using audit events."""
    event = (
        db.query(AuditLog)
        .filter(
            AuditLog.event_type == "USER_STATUS_CHANGE",
            AuditLog.target_user_id == user.id,
            AuditLog.at <= at,
        )
        .order_by(AuditLog.at.desc(), AuditLog.id.desc())
        .first()
    )
    if event and event.after_state and "status" in event.after_state:
        return event.after_state["status"]
    return user.status


def _reconstruct_job_state_at(db: Session, job: Job, at: datetime) -> Dict[str, Any]:
    """Reconstruct a job's stage and actors at historical time `at` using audit events."""
    event = (
        db.query(AuditLog)
        .filter(
            AuditLog.job_id == job.id,
            AuditLog.at <= at,
            AuditLog.event_type.in_(["JOB_CREATE", "JOB_ACTION", "JOB_OVERRIDE", "APPROVAL_DECISION"]),
        )
        .order_by(AuditLog.at.desc(), AuditLog.id.desc())
        .first()
    )
    if event and event.after_state:
        return {
            "stage": event.after_state.get("stage", job.stage),
            "prepared_by": event.after_state.get("prepared_by", job.prepared_by),
            "checked_by": event.after_state.get("checked_by", job.checked_by),
            "filed_by": event.after_state.get("filed_by", job.filed_by),
            "cycle": event.after_state.get("cycle", job.cycle),
        }
    return {
        "stage": job.stage,
        "prepared_by": job.prepared_by,
        "checked_by": job.checked_by,
        "filed_by": job.filed_by,
        "cycle": job.cycle,
    }


def decide(
    db: Session,
    user_id: str,
    action: str,
    job: Optional[Union[Job, Dict[str, Any]]],
    at: Optional[datetime] = None,
    reason: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> DecisionResponse:
    """Evaluate whether user_id is authorized to perform action on job as of time `at`."""
    eval_time = at or get_now()
    if eval_time.tzinfo is None:
        eval_time = eval_time.replace(tzinfo=timezone.utc)
    else:
        eval_time = eval_time.astimezone(timezone.utc)

    checks: List[CheckDetail] = []
    matched_grants: List[str] = []
    denying_grants: List[str] = []
    required_perm: Optional[str] = None

    try:
        # -----------------------------------------------------------------
        # 1. USER_KNOWN & USER_TYPE COMPATIBILITY
        # -----------------------------------------------------------------
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            checks.append(CheckDetail(
                code="USER_KNOWN",
                passed=False,
                detail=f"User '{user_id}' does not exist in directory"
            ))
            return DecisionResponse(
                allowed=False,
                outcome="DENY",
                primary_reason="USER_UNKNOWN",
                checks=checks,
                matched_grants=[],
                denying_grants=[],
                required_permission=ACTION_TO_PERMISSION.get(action),
                evaluated_at=eval_time,
            )

        # User type restrictions
        if user.type == "client" and action != "view":
            checks.append(CheckDetail(
                code="USER_KNOWN",
                passed=False,
                detail=f"Client users are restricted to 'view' action only; '{action}' is disallowed"
            ))
            user_type_error = "CLIENT_USER_RESTRICTED"
        elif user.type == "system" and action not in ("create", "update_unfiled"):
            checks.append(CheckDetail(
                code="USER_KNOWN",
                passed=False,
                detail=f"System users are restricted to 'create' and 'update_unfiled'; '{action}' is disallowed"
            ))
            user_type_error = "SYSTEM_USER_RESTRICTED"
        else:
            checks.append(CheckDetail(
                code="USER_KNOWN",
                passed=True,
                detail=f"User '{user.id}' is known and user type '{user.type}' is compatible with action '{action}'"
            ))
            user_type_error = None

        # -----------------------------------------------------------------
        # 2. USER_ACTIVE
        # -----------------------------------------------------------------
        user_status_at = _reconstruct_user_status_at(db, user, eval_time)
        if user_status_at == "absent" and action != "view":
            checks.append(CheckDetail(
                code="USER_ACTIVE",
                passed=False,
                detail=f"User '{user.id}' was absent at {eval_time.isoformat()}; cannot perform active actions"
            ))
            user_active_passed = False
        else:
            checks.append(CheckDetail(
                code="USER_ACTIVE",
                passed=True,
                detail=f"User status is '{user_status_at}'; authorized for evaluation"
            ))
            user_active_passed = True

        # -----------------------------------------------------------------
        # 3. JOB_DATA_COMPLETE
        # -----------------------------------------------------------------
        # Extract job attributes
        job_obj: Optional[Job] = job if isinstance(job, Job) else None
        job_data: Dict[str, Any] = {}
        if isinstance(job, Job):
            # Reconstruct historical state if needed
            hist = _reconstruct_job_state_at(db, job, eval_time)
            job_data = {
                "id": job.id,
                "ref": job.ref,
                "client_id": job.client_id,
                "branch_id": job.branch_id,
                "direction": job.direction,
                "mode": job.mode,
                "stage": hist["stage"],
                "prepared_by": hist["prepared_by"],
                "checked_by": hist["checked_by"],
                "filed_by": hist["filed_by"],
                "cycle": hist["cycle"],
                "assigned_to": job.assigned_to,
            }
        elif isinstance(job, dict):
            job_data = job
        else:
            job_data = {}

        # Validate job fields
        req_fields = ["client_id", "branch_id", "direction", "mode"]
        if action != "create":
            req_fields.append("stage")

        missing = [f for f in req_fields if not job_data.get(f)]
        invalid_direction = job_data.get("direction") not in VALID_DIRECTIONS if "direction" in job_data else False
        invalid_mode = job_data.get("mode") not in VALID_MODES if "mode" in job_data else False
        invalid_stage = (job_data.get("stage") not in VALID_STAGES) if (action != "create" and "stage" in job_data) else False

        if missing or invalid_direction or invalid_mode or invalid_stage:
            details = []
            if missing:
                details.append(f"Missing attributes: {missing}")
            if invalid_direction:
                details.append(f"Invalid direction: '{job_data.get('direction')}'")
            if invalid_mode:
                details.append(f"Invalid mode: '{job_data.get('mode')}'")
            if invalid_stage:
                details.append(f"Invalid stage: '{job_data.get('stage')}'")
            checks.append(CheckDetail(
                code="JOB_DATA_COMPLETE",
                passed=False,
                detail="; ".join(details)
            ))
            job_complete = False
        else:
            checks.append(CheckDetail(
                code="JOB_DATA_COMPLETE",
                passed=True,
                detail="Job data contains all mandatory dimensional attributes and valid stage"
            ))
            job_complete = True

        # -----------------------------------------------------------------
        # 4. ACTION_KNOWN
        # -----------------------------------------------------------------
        if action not in ACTION_TO_PERMISSION:
            checks.append(CheckDetail(
                code="ACTION_KNOWN",
                passed=False,
                detail=f"Action '{action}' is not in the system permission catalogue"
            ))
            action_known = False
        else:
            required_perm = ACTION_TO_PERMISSION[action]
            checks.append(CheckDetail(
                code="ACTION_KNOWN",
                passed=True,
                detail=f"Action '{action}' maps to permission '{required_perm}'"
            ))
            action_known = True

        # -----------------------------------------------------------------
        # 5. STAGE_VALID
        # -----------------------------------------------------------------
        stage = job_data.get("stage")
        stage_valid = True
        stage_detail = f"Stage '{stage}' is valid for action '{action}'"

        if action == "prepare":
            if stage not in ("CONFIRMED", "REOPENED"):
                stage_valid = False
                stage_detail = f"Action 'prepare' requires stage CONFIRMED or REOPENED, found '{stage}'"
        elif action == "check":
            if stage != "PREPARED":
                stage_valid = False
                stage_detail = f"Action 'check' requires stage PREPARED, found '{stage}'"
        elif action == "file":
            if stage != "CHECKED":
                stage_valid = False
                stage_detail = f"Action 'file' requires stage CHECKED, found '{stage}'"
        elif action == "cancel":
            if stage not in ("CONFIRMED", "PREPARED", "CHECKED", "REOPENED"):
                stage_valid = False
                stage_detail = f"Action 'cancel' cannot cancel filed or already cancelled jobs; stage is '{stage}'"
        elif action == "cancel_filed":
            if stage != "FILED":
                stage_valid = False
                stage_detail = f"Action 'cancel_filed' requires stage FILED, found '{stage}'"
        elif action == "reopen":
            if stage not in ("FILED", "CANCELLED"):
                stage_valid = False
                stage_detail = f"Action 'reopen' requires stage FILED or CANCELLED, found '{stage}'"
        elif action == "update_unfiled":
            if stage != "CONFIRMED":
                stage_valid = False
                stage_detail = f"Action 'update_unfiled' only allowed in CONFIRMED stage, found '{stage}'"
        elif action == "reassign":
            if stage not in ("CONFIRMED", "PREPARED", "CHECKED", "REOPENED"):
                stage_valid = False
                stage_detail = f"Action 'reassign' only allowed on unfiled non-cancelled stages, found '{stage}'"
        elif action == "override_send_back":
            if stage not in ("PREPARED", "CHECKED"):
                stage_valid = False
                stage_detail = f"Action 'override_send_back' can only send back PREPARED or CHECKED jobs; found '{stage}'"

        checks.append(CheckDetail(
            code="STAGE_VALID",
            passed=stage_valid,
            detail=stage_detail
        ))

        # -----------------------------------------------------------------
        # 6. GRANT_COVERS_SCOPE
        # -----------------------------------------------------------------
        grant_covers = False
        grant_error_code = "NO_GRANT"

        if not required_perm:
            checks.append(CheckDetail(
                code="GRANT_COVERS_SCOPE",
                passed=False,
                detail="No required permission identified"
            ))
        elif user_status_at == "absent" and action != "view":
            # Absent users' own grants do not apply
            checks.append(CheckDetail(
                code="GRANT_COVERS_SCOPE",
                passed=False,
                detail="User is absent; grants do not apply while absent"
            ))
            grant_error_code = "USER_ABSENT"
        else:
            # Look up active grants for user as of eval_time
            # Active grants: created_at <= eval_time, valid_from <= eval_time,
            # valid_to is null or valid_to >= eval_time,
            # revoked_at is null or revoked_at > eval_time.
            raw_grants = (
                db.query(Grant)
                .filter(
                    Grant.user_id == user.id,
                    Grant.created_at <= eval_time,
                    Grant.valid_from <= eval_time,
                    or_(Grant.valid_to.is_(None), Grant.valid_to >= eval_time),
                    or_(Grant.revoked_at.is_(None), Grant.revoked_at > eval_time),
                )
                .all()
            )

            # Client users can never see another client's jobs
            if user.type == "client":
                if job_data.get("client_id") != user.client_id:
                    checks.append(CheckDetail(
                        code="GRANT_COVERS_SCOPE",
                        passed=False,
                        detail=f"Client user cannot access jobs of another client '{job_data.get('client_id')}'"
                    ))
                    grant_error_code = "NO_GRANT"
                    raw_grants = []  # Discard grants outside client scope

            for g in raw_grants:
                # Check if role contains required permission as of eval_time
                rp = (
                    db.query(RolePermission)
                    .filter(
                        RolePermission.role_id == g.role_id,
                        RolePermission.permission == required_perm,
                        RolePermission.added_at <= eval_time,
                        or_(RolePermission.removed_at.is_(None), RolePermission.removed_at > eval_time),
                    )
                    .first()
                )
                if not rp:
                    continue

                # Check dimensional scope match against job_data
                # NULL in grant means ALL (wildcard)
                client_match = (g.client_id is None) or (g.client_id == job_data.get("client_id"))
                branch_match = (g.branch_id is None) or (g.branch_id == job_data.get("branch_id"))
                direction_match = (g.direction is None) or (g.direction == job_data.get("direction"))
                mode_match = (g.mode is None) or (g.mode == job_data.get("mode"))

                if client_match and branch_match and direction_match and mode_match:
                    if g.effect == "deny":
                        denying_grants.append(g.id)
                    else:
                        matched_grants.append(g.id)

            if denying_grants:
                grant_covers = False
                grant_error_code = "EXPLICIT_DENY"
                checks.append(CheckDetail(
                    code="GRANT_COVERS_SCOPE",
                    passed=False,
                    detail=f"Explicit DENY grant(s) {denying_grants} override all allow grants"
                ))
            elif matched_grants:
                grant_covers = True
                checks.append(CheckDetail(
                    code="GRANT_COVERS_SCOPE",
                    passed=True,
                    detail=f"Scope covered by active allow grant(s): {matched_grants}"
                ))
            else:
                grant_covers = False
                grant_error_code = "NO_GRANT"
                checks.append(CheckDetail(
                    code="GRANT_COVERS_SCOPE",
                    passed=False,
                    detail=f"No active grant grants permission '{required_perm}' for job scope ({job_data.get('client_id')}, {job_data.get('branch_id')}, {job_data.get('direction')}, {job_data.get('mode')})"
                ))

        # -----------------------------------------------------------------
        # 7. SOD_OK (Separation of Duties)
        # -----------------------------------------------------------------
        sod_ok = True
        sod_error_code = None
        sod_detail = "Separation of duties rules satisfied"

        if action == "check":
            prepared_by = job_data.get("prepared_by")
            if prepared_by and prepared_by == user.id:
                sod_ok = False
                sod_error_code = "SOD_VIOLATION_MAKER_CHECKER"
                sod_detail = f"Maker-Checker conflict: user '{user.id}' prepared this job in cycle {job_data.get('cycle', 1)} and cannot check it"

        elif action == "approve_sensitive":
            requester_id = (context or {}).get("requested_by")
            if requester_id and requester_id == user.id:
                sod_ok = False
                sod_error_code = "SOD_VIOLATION_SELF_APPROVAL"
                sod_detail = f"Self-approval conflict: requester '{requester_id}' cannot approve their own sensitive action request"

        checks.append(CheckDetail(
            code="SOD_OK",
            passed=sod_ok,
            detail=sod_detail
        ))

        # -----------------------------------------------------------------
        # 8. REASON_PROVIDED
        # -----------------------------------------------------------------
        reason_required = action in ("override_send_back", "cancel_filed", "reopen")
        reason_clean = (reason or "").strip()
        reason_ok = True
        reason_detail = "Reason provided or not required for this action"

        if reason_required:
            if len(reason_clean) < 3:
                reason_ok = False
                reason_detail = f"Action '{action}' is sensitive or override; a descriptive reason is mandatory"

        checks.append(CheckDetail(
            code="REASON_PROVIDED",
            passed=reason_ok,
            detail=reason_detail
        ))

        # -----------------------------------------------------------------
        # Evaluate primary reason according to strict precedence
        # -----------------------------------------------------------------
        primary_reason: Optional[str] = None
        outcome: str = "DENY"
        allowed: bool = False

        if user_type_error:
            primary_reason = user_type_error
        elif not user_active_passed:
            primary_reason = "USER_ABSENT"
        elif not job_complete:
            primary_reason = "JOB_INCOMPLETE"
        elif not action_known:
            primary_reason = "ACTION_UNKNOWN"
        elif not stage_valid:
            primary_reason = "STAGE_INVALID"
        elif not grant_covers:
            primary_reason = grant_error_code
        elif not sod_ok:
            primary_reason = sod_error_code
        elif not reason_ok:
            primary_reason = "REASON_REQUIRED"

        if primary_reason is None:
            # All 8 checks passed!
            if action in ("cancel_filed", "reopen"):
                outcome = "NEEDS_APPROVAL"
                allowed = True
            else:
                outcome = "ALLOW"
                allowed = True
        else:
            outcome = "DENY"
            allowed = False

        return DecisionResponse(
            allowed=allowed,
            outcome=outcome,
            primary_reason=primary_reason,
            checks=checks,
            matched_grants=matched_grants,
            denying_grants=denying_grants,
            required_permission=required_perm,
            evaluated_at=eval_time,
        )

    except Exception as exc:
        logger.exception(f"Decision engine indeterminate error: {exc}")
        # UNSURE = DENY: Audit log indeterminate error and fail closed
        checks.append(CheckDetail(
            code="ENGINE_INTERNAL",
            passed=False,
            detail=f"Indeterminate engine error: {str(exc)}"
        ))
        return DecisionResponse(
            allowed=False,
            outcome="DENY",
            primary_reason="INDETERMINATE",
            checks=checks,
            matched_grants=[],
            denying_grants=[],
            required_permission=required_perm,
            evaluated_at=eval_time,
        )


def explain_compare(
    decision_a: DecisionResponse,
    decision_b: DecisionResponse,
    user_a_id: str,
    user_b_id: str,
) -> str:
    """Produce a plain-English explanation comparing why User A and User B received their decisions."""
    if decision_a.allowed and not decision_b.allowed:
        return (
            f"User '{user_a_id}' is ALLOWED ({decision_a.outcome}) via grants {decision_a.matched_grants}, "
            f"whereas User '{user_b_id}' is DENIED due to {decision_b.primary_reason}."
        )
    elif not decision_a.allowed and decision_b.allowed:
        return (
            f"User '{user_a_id}' is DENIED due to {decision_a.primary_reason}, "
            f"whereas User '{user_b_id}' is ALLOWED ({decision_b.outcome}) via grants {decision_b.matched_grants}."
        )
    elif decision_a.allowed and decision_b.allowed:
        return f"Both users are authorized. User '{user_a_id}' uses {decision_a.matched_grants}; User '{user_b_id}' uses {decision_b.matched_grants}."
    else:
        return (
            f"Both users are DENIED. User '{user_a_id}' blocked by {decision_a.primary_reason}; "
            f"User '{user_b_id}' blocked by {decision_b.primary_reason}."
        )
