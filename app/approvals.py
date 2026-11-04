"""Two-person approval workflows for sensitive actions on shipments."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import update, and_
from fastapi import HTTPException, status

from app.clock import get_now
from app.models import User, Job, Approval, AuditLog
from app.decision import decide
from app.audit import log_audit_event


def approve_request(
    db: Session,
    approver: User,
    approval_id: str,
    reason: str,
) -> Approval:
    """Approve a pending sensitive action with two-person rule & fail-closed stale check."""
    now = get_now()
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Approval request '{approval_id}' not found")

    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval request is not pending (current status: '{approval.status}')",
        )

    # 1. SoD: Approver must differ from requester
    if approver.id == approval.requested_by:
        log_audit_event(
            db=db,
            actor_id=approver.id,
            actor_type=approver.type,
            event_type="APPROVAL_DECISION",
            action="approve",
            decision="DENY",
            job_id=approval.job_id,
            reason_codes=["SOD_VIOLATION_SELF_APPROVAL"],
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Separation of duties violation: approver cannot be the same user who requested the sensitive action",
        )

    job = db.query(Job).filter(Job.id == approval.job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Associated job '{approval.job_id}' not found")

    # 2. Approver must hold job.approve_sensitive in scope
    context = {"requested_by": approval.requested_by}
    decision = decide(
        db,
        user_id=approver.id,
        action="approve_sensitive",
        job=job,
        at=now,
        context=context,
    )

    if not decision.allowed:
        log_audit_event(
            db=db,
            actor_id=approver.id,
            actor_type=approver.type,
            event_type="APPROVAL_DECISION",
            action="approve",
            decision="DENY",
            job_id=job.id,
            reason_codes=[decision.primary_reason or "UNAUTHORIZED"],
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Approver lacks scope: {decision.primary_reason}",
        )

    # 3. Fail-closed stale check: verify stage is still valid
    expected_stage_valid = False
    if approval.action == "cancel_filed" and job.stage == "FILED":
        expected_stage_valid = True
    elif approval.action == "reopen" and job.stage in ("FILED", "CANCELLED"):
        expected_stage_valid = True

    if not expected_stage_valid:
        # State changed mid-flight -> mark STALE and fail closed
        approval.status = "stale"
        approval.decided_by = approver.id
        approval.decided_at = now
        log_audit_event(
            db=db,
            actor_id=approver.id,
            actor_type=approver.type,
            event_type="APPROVAL_DECISION",
            action="mark_stale",
            decision="FAIL_CLOSED",
            job_id=job.id,
            reason_codes=["JOB_STAGE_CHANGED_MID_APPROVAL"],
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job state changed since approval request was submitted; approval marked STALE",
        )

    # Execute state change
    before_state = {"stage": job.stage, "cycle": job.cycle}
    if approval.action == "cancel_filed":
        job.stage = "CANCELLED"
    elif approval.action == "reopen":
        job.stage = "REOPENED"
        job.cycle += 1
        job.prepared_by = None
        job.checked_by = None
        job.filed_by = None

    job.updated_at = now
    approval.status = "approved"
    approval.decided_by = approver.id
    approval.decided_at = now

    after_state = {
        "stage": job.stage,
        "cycle": job.cycle,
        "approval_id": approval.id,
        "reason": reason,
    }

    log_audit_event(
        db=db,
        actor_id=approver.id,
        actor_type=approver.type,
        event_type="APPROVAL_DECISION",
        action="approve",
        decision="EXECUTE",
        job_id=job.id,
        grant_ids_used=decision.matched_grants,
        before_state=before_state,
        after_state=after_state,
    )

    db.commit()
    db.refresh(approval)
    return approval


def reject_request(
    db: Session,
    approver: User,
    approval_id: str,
    reason: str,
) -> Approval:
    """Reject a pending sensitive action request."""
    now = get_now()
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Approval request '{approval_id}' not found")

    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval request is not pending (status: '{approval.status}')",
        )

    approval.status = "rejected"
    approval.decided_by = approver.id
    approval.decided_at = now

    log_audit_event(
        db=db,
        actor_id=approver.id,
        actor_type=approver.type,
        event_type="APPROVAL_DECISION",
        action="reject",
        decision="EXECUTE",
        job_id=approval.job_id,
        reason_codes=[reason],
        after_state={"approval_id": approval.id, "status": "rejected", "reason": reason},
    )

    db.commit()
    db.refresh(approval)
    return approval
