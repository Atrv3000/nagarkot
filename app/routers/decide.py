"""Decision dry-run and comparative explainability endpoints."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User, Job
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
    at: Optional[str] = Query(None, description="Optional ISO timestamp for historical 'as of' replay"),
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dry run a decision with complete 8-stage evaluation trace. Not logged to audit log."""
    eval_time = _parse_time(at)
    job = db.query(Job).filter(Job.id == job_id).first()
    return decide(db, user_id=user_id, action=action, job=job, at=eval_time)


@router.get("/explain/compare", response_model=CompareResponse)
def compare_decisions(
    users: str = Query(..., description="Comma-separated user IDs, e.g. user_a,user_b"),
    action: str = Query(..., description="Action to evaluate"),
    job_id: str = Query(..., description="Target Job ID"),
    at: Optional[str] = Query(None, description="Optional ISO timestamp for historical replay"),
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Side-by-side comparison explaining why User A is allowed and User B is denied (or vice versa)."""
    user_ids = [u.strip() for u in users.split(",") if u.strip()]
    if len(user_ids) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The 'users' query parameter must specify exactly two user IDs, e.g. 'users=asha-rao,rohit-mehta'",
        )

    user_a_id, user_b_id = user_ids[0], user_ids[1]
    eval_time = _parse_time(at)
    job = db.query(Job).filter(Job.id == job_id).first()

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
