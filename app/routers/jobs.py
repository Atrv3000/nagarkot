"""Job listing, actions, lifecycle management, history, and who-could endpoints."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, get_actor_run_id
from app.models import User, Job, AuditLog
from app.scope import compile_jobs_view_predicate, paginate_jobs_query
from app.jobs import create_job, patch_job, execute_job_action, get_job_who_could
from app.schemas import (
    JobCreate,
    JobPatch,
    JobActionRequest,
    JobResponse,
    JobQueueResponse,
    WhoCouldResponse,
    AuditLogResponse,
)

router = APIRouter(tags=["Jobs & Shipments"])


def _redact_for_client(job: Job, caller: User) -> JobResponse:
    """Redact internal operational fields if caller is a client user."""
    resp = JobResponse.model_validate(job)
    if caller.type == "client":
        resp.assigned_to = None
        resp.prepared_by = None
        resp.checked_by = None
        resp.filed_by = None
        resp.internal_notes = None
    return resp


@router.get("/jobs", response_model=JobQueueResponse)
def list_jobs(
    cursor: Optional[str] = Query(None, description="Keyset cursor for pagination"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve jobs the caller is authorized to view. Keyset paginated."""
    predicate = compile_jobs_view_predicate(db, caller)
    query = db.query(Job).filter(predicate)

    # Calculate total count from the same predicate
    total_count = query.count()
    items, next_cursor = paginate_jobs_query(query, cursor=cursor, limit=limit)

    return JobQueueResponse(
        count=total_count,
        items=[_redact_for_client(j, caller) for j in items],
        next_cursor=next_cursor,
    )


@router.get("/jobs/{id}", response_model=JobResponse)
def get_job_by_id(
    id: str,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve single job details if within caller's view scope."""
    predicate = compile_jobs_view_predicate(db, caller)
    job = db.query(Job).filter(Job.id == id, predicate).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{id}' not found or not visible within your scope",
        )
    return _redact_for_client(job, caller)


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_new_job(
    data: JobCreate,
    caller: User = Depends(get_current_user),
    actor_run_id: Optional[str] = Depends(get_actor_run_id),
    db: Session = Depends(get_db),
):
    """Create a new job in CONFIRMED stage (requires job.create)."""
    job = create_job(db, caller, data, actor_run_id=actor_run_id)
    return _redact_for_client(job, caller)


@router.patch("/jobs/{id}", response_model=JobResponse)
def patch_unfiled_job(
    id: str,
    data: JobPatch,
    caller: User = Depends(get_current_user),
    actor_run_id: Optional[str] = Depends(get_actor_run_id),
    db: Session = Depends(get_db),
):
    """Update allow-listed fields on a CONFIRMED job (requires job.update_unfiled)."""
    job = patch_job(db, caller, id, data, actor_run_id=actor_run_id)
    return _redact_for_client(job, caller)


@router.post("/jobs/{id}/actions/{action}")
def perform_job_action(
    id: str,
    action: str,
    request_data: JobActionRequest = JobActionRequest(),
    caller: User = Depends(get_current_user),
    actor_run_id: Optional[str] = Depends(get_actor_run_id),
    db: Session = Depends(get_db),
):
    """Execute lifecycle action (prepare, check, file, cancel, reassign, override_send_back, cancel_filed, reopen)."""
    return execute_job_action(db, caller, id, action, request_data, actor_run_id=actor_run_id)


@router.get("/jobs/{id}/who-could", response_model=WhoCouldResponse)
def get_who_could(
    id: str,
    action: str = Query(..., description="Action to analyze"),
    at: Optional[str] = Query(None, description="Optional historical ISO timestamp"),
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Audit query: identify everyone who could have performed an action at timestamp `at`."""
    eval_time = None
    if at:
        eval_time = datetime.fromisoformat(at)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)
    return get_job_who_could(db, job_id=id, action=action, at=eval_time)


@router.get("/jobs/{id}/history", response_model=List[AuditLogResponse])
def get_job_history(
    id: str,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve chronological audit history of all state changes and events for a job."""
    # Ensure caller has view rights on the job
    predicate = compile_jobs_view_predicate(db, caller)
    job = db.query(Job).filter(Job.id == id, predicate).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{id}' not found")

    events = (
        db.query(AuditLog)
        .filter(AuditLog.job_id == id)
        .order_by(AuditLog.at.asc(), AuditLog.id.asc())
        .all()
    )
    return events
