"""Job lifecycle management, state transitions, concurrency control, and history queries."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import update, and_
from fastapi import HTTPException, status

from app.clock import get_now
from app.models import (
    User,
    Job,
    Approval,
    AuditLog,
)
from app.decision import decide
from app.audit import log_audit_event
from app.schemas import JobCreate, JobPatch, JobActionRequest, ActorWhoCould, WhoCouldResponse


def create_job(
    db: Session,
    caller: User,
    data: JobCreate,
    actor_run_id: Optional[str] = None,
) -> Job:
    """Create a new job in CONFIRMED stage."""
    now = get_now()

    prospective_data = {
        "client_id": data.client_id,
        "branch_id": data.branch_id,
        "direction": data.direction,
        "mode": data.mode,
        "stage": "CONFIRMED",
    }
    decision = decide(db, user_id=caller.id, action="create", job=prospective_data, at=now)
    if not decision.allowed:
        log_audit_event(
            db=db,
            actor_id=caller.id,
            actor_type=caller.type,
            actor_run_id=actor_run_id,
            event_type="DENIED_ATTEMPT",
            action="create",
            decision="DENY",
            reason_codes=[decision.primary_reason or "UNAUTHORIZED"],
            after_state=prospective_data,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: {decision.primary_reason}",
        )

    job_id = f"JOB-{uuid.uuid4().hex[:10]}"
    job = Job(
        id=job_id,
        ref=data.ref,
        client_id=data.client_id,
        branch_id=data.branch_id,
        direction=data.direction,
        mode=data.mode,
        stage="CONFIRMED",
        assigned_to=data.assigned_to,
        internal_notes=data.internal_notes,
        cycle=1,
        created_by=caller.id,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.flush()

    log_audit_event(
        db=db,
        actor_id=caller.id,
        actor_type=caller.type,
        actor_run_id=actor_run_id,
        event_type="JOB_CREATE",
        action="create",
        decision="EXECUTE",
        job_id=job.id,
        grant_ids_used=decision.matched_grants,
        after_state={
            "ref": job.ref,
            "client_id": job.client_id,
            "branch_id": job.branch_id,
            "direction": job.direction,
            "mode": job.mode,
            "stage": job.stage,
        },
    )
    db.commit()
    db.refresh(job)
    return job


def patch_job(
    db: Session,
    caller: User,
    job_id: str,
    data: JobPatch,
    actor_run_id: Optional[str] = None,
) -> Job:
    """Patch allow-listed fields on a CONFIRMED job."""
    now = get_now()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")

    decision = decide(db, user_id=caller.id, action="update_unfiled", job=job, at=now)
    if not decision.allowed:
        log_audit_event(
            db=db,
            actor_id=caller.id,
            actor_type=caller.type,
            actor_run_id=actor_run_id,
            event_type="DENIED_ATTEMPT",
            action="update_unfiled",
            decision="DENY",
            job_id=job.id,
            reason_codes=[decision.primary_reason or "UNAUTHORIZED"],
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: {decision.primary_reason}",
        )

    before_state = {"assigned_to": job.assigned_to, "internal_notes": job.internal_notes}

    # Conditional update on stage == CONFIRMED
    stmt = (
        update(Job)
        .where(and_(Job.id == job.id, Job.stage == "CONFIRMED"))
        .values(
            assigned_to=data.assigned_to if data.assigned_to is not None else job.assigned_to,
            internal_notes=data.internal_notes if data.internal_notes is not None else job.internal_notes,
            updated_at=now,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict: job was modified or stage is no longer CONFIRMED",
        )

    db.refresh(job)
    after_state = {"assigned_to": job.assigned_to, "internal_notes": job.internal_notes}

    log_audit_event(
        db=db,
        actor_id=caller.id,
        actor_type=caller.type,
        actor_run_id=actor_run_id,
        event_type="JOB_ACTION",
        action="update_unfiled",
        decision="EXECUTE",
        job_id=job.id,
        grant_ids_used=decision.matched_grants,
        before_state=before_state,
        after_state=after_state,
    )
    db.commit()
    return job


def execute_job_action(
    db: Session,
    caller: User,
    job_id: str,
    action: str,
    request_data: JobActionRequest,
    actor_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute or submit approval for a job lifecycle action."""
    now = get_now()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")

    is_override = (action == "override_send_back")

    decision = decide(
        db,
        user_id=caller.id,
        action=action,
        job=job,
        at=now,
        reason=request_data.reason,
    )

    if not decision.allowed:
        log_audit_event(
            db=db,
            actor_id=caller.id,
            actor_type=caller.type,
            actor_run_id=actor_run_id,
            event_type="DENIED_ATTEMPT",
            action=action,
            decision="DENY",
            job_id=job.id,
            reason_codes=[decision.primary_reason or "UNAUTHORIZED"],
            is_override=is_override,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: {decision.primary_reason}",
        )

    # Sensitive actions return NEEDS_APPROVAL and spawn an Approval request
    if decision.outcome == "NEEDS_APPROVAL":
        approval_id = f"APP-{uuid.uuid4().hex[:10]}"
        approval = Approval(
            id=approval_id,
            job_id=job.id,
            action=action,
            requested_by=caller.id,
            reason=request_data.reason or "No reason specified",
            status="pending",
            created_at=now,
        )
        db.add(approval)
        db.flush()

        log_audit_event(
            db=db,
            actor_id=caller.id,
            actor_type=caller.type,
            actor_run_id=actor_run_id,
            event_type="APPROVAL_REQUESTED",
            action=action,
            decision="NEEDS_APPROVAL",
            job_id=job.id,
            grant_ids_used=decision.matched_grants,
            after_state={"approval_id": approval.id, "action": action, "status": "pending"},
        )
        db.commit()
        return {
            "status": "NEEDS_APPROVAL",
            "approval_id": approval.id,
            "message": "Sensitive action submitted for 2-person authorization to Approver",
        }

    # Standard state transition
    before_state = {
        "stage": job.stage,
        "prepared_by": job.prepared_by,
        "checked_by": job.checked_by,
        "filed_by": job.filed_by,
        "assigned_to": job.assigned_to,
        "cycle": job.cycle,
    }

    expected_stage = job.stage
    updates: Dict[str, Any] = {"updated_at": now}
    is_override = False

    if action == "prepare":
        updates["stage"] = "PREPARED"
        updates["prepared_by"] = caller.id
    elif action == "check":
        updates["stage"] = "CHECKED"
        updates["checked_by"] = caller.id
    elif action == "file":
        updates["stage"] = "FILED"
        updates["filed_by"] = caller.id
    elif action == "cancel":
        updates["stage"] = "CANCELLED"
    elif action == "reassign":
        updates["assigned_to"] = request_data.new_assignee_id
    elif action == "override_send_back":
        is_override = True
        if job.stage == "PREPARED":
            updates["stage"] = "CONFIRMED"
            updates["prepared_by"] = None
        elif job.stage == "CHECKED":
            updates["stage"] = "PREPARED"
            updates["checked_by"] = None

    stmt = (
        update(Job)
        .where(and_(Job.id == job.id, Job.stage == expected_stage))
        .values(**updates)
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Concurrency conflict: job stage changed concurrently",
        )

    db.refresh(job)
    after_state = {
        "stage": job.stage,
        "prepared_by": job.prepared_by,
        "checked_by": job.checked_by,
        "filed_by": job.filed_by,
        "assigned_to": job.assigned_to,
        "cycle": job.cycle,
    }

    log_audit_event(
        db=db,
        actor_id=caller.id,
        actor_type=caller.type,
        actor_run_id=actor_run_id,
        event_type="JOB_OVERRIDE" if is_override else "JOB_ACTION",
        action=action,
        decision="EXECUTE",
        job_id=job.id,
        grant_ids_used=decision.matched_grants,
        before_state=before_state,
        after_state=after_state,
        is_override=is_override,
    )
    db.commit()
    return {
        "status": "EXECUTED",
        "job_id": job.id,
        "action": action,
        "current_stage": job.stage,
    }


def get_job_who_could(
    db: Session,
    job_id: str,
    action: str,
    at: Optional[datetime] = None,
) -> WhoCouldResponse:
    """Identify every user who possessed permission to perform action on job_id at timestamp `at`."""
    eval_time = at or get_now()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")

    users = db.query(User).all()
    actors_who_could: List[ActorWhoCould] = []

    for u in users:
        dec = decide(db, user_id=u.id, action=action, job=job, at=eval_time)
        if dec.allowed:
            actors_who_could.append(
                ActorWhoCould(
                    user_id=u.id,
                    name=u.name,
                    user_type=u.type,
                    status=u.status,
                    grants_held=dec.matched_grants,
                )
            )

    # Look up actual actor from audit log for this action on the job
    actual_event = (
        db.query(AuditLog)
        .filter(
            AuditLog.job_id == job.id,
            AuditLog.action == action,
            AuditLog.decision == "EXECUTE",
        )
        .order_by(AuditLog.at.asc())
        .first()
    )
    actual_actor = None
    if actual_event:
        actual_actor = {
            "actor_id": actual_event.actor_id,
            "performed_at": actual_event.at.isoformat(),
            "grant_ids_used": actual_event.grant_ids_used,
        }

    return WhoCouldResponse(
        job_id=job.id,
        action=action,
        evaluated_at=eval_time,
        actors_who_could=actors_who_could,
        actual_actor=actual_actor,
    )
