"""Decision dry-run and comparative explainability endpoints."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, caller_has_access_or_audit
from app.models import User, Job
from app.scope import compile_jobs_view_predicate
from app.decision import decide, explain_compare
from app.schemas import DecisionResponse, CompareResponse

router = APIRouter(tags=["Decisions & Explainability"])


def _parse_time(at_str: Optional[str]) -> Optional[datetime]:
    if not at_str:
        return None
    dt = datetime.fromisoformat(at_str)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/decide", response_model=DecisionResponse)
def evaluate_decision(
    user_id: str = Query(..., description="Target user ID to evaluate"),
    action: str = Query(..., description="Action to evaluate"),
    job_id: str = Query(..., description="Target Job ID"),
    reason: Optional[str] = Query(None, description="Optional action reason"),
    at: Optional[str] = Query(None, description="Optional ISO timestamp for historical 'as of' replay"),
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dry run a decision with complete 8-stage evaluation trace. Not logged to audit log.
    Enforces client data isolation, and requires self-query or access.manage / audit.view to evaluate others.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")

    # Client user isolation: client user can only evaluate jobs belonging to their own client
    if caller.type == "client" and job.client_id != caller.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")

    # Cross-user authorization check: evaluating other users requires access.manage or audit.view
    if user_id != caller.id:
        if caller.type == "client" or not caller_has_access_or_audit(db, caller):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: evaluating decisions for other users requires access.manage or audit.view permission",
            )

    eval_time = _parse_time(at)
    return decide(db, user_id=user_id, action=action, job=job, at=eval_time, reason=reason)


@router.get("/explain/compare", response_model=CompareResponse)
def compare_decisions(
    users: str = Query(..., description="Comma-separated user IDs, e.g. user_a,user_b"),
    action: str = Query(..., description="Action to evaluate"),
    job_id: str = Query(..., description="Target Job ID"),
    at: Optional[str] = Query(None, description="Optional ISO timestamp for historical replay"),
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Side-by-side comparison explaining why User A is allowed and User B is denied (or vice versa).
    Requires job visibility and access.manage or audit.view permission.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")

    # Client user isolation
    if caller.type == "client" and job.client_id != caller.client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")

    # Comparative explainability requires administrative or audit access
    if caller.type == "client" or not caller_has_access_or_audit(db, caller):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: comparative explainability requires access.manage or audit.view permission",
        )

    user_ids = [u.strip() for u in users.split(",") if u.strip()]
    if len(user_ids) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The 'users' query parameter must specify exactly two user IDs, e.g. 'users=asha-rao,rohit-mehta'",
        )

    user_a_id, user_b_id = user_ids[0], user_ids[1]
    eval_time = _parse_time(at)

    decision_a = decide(db, user_id=user_a_id, action=action, job=job, at=eval_time)
    decision_b = decide(db, user_id=user_b_id, action=action, job=job, at=eval_time)

    summary = explain_compare(decision_a, decision_b, user_a_id, user_b_id)

    return CompareResponse(
        user_a_id=user_a_id,
        user_b_id=user_b_id,
        user_a_decision=decision_a,
        user_b_decision=decision_b,
        comparison_summary=summary,
    )
