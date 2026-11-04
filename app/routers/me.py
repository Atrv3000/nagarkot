"""Personal action queue endpoint for the authenticated user."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User, Job
from app.scope import compile_my_queue_predicate, paginate_jobs_query
from app.schemas import JobResponse, JobQueueResponse

router = APIRouter(tags=["Personal Action Queue"])


@router.get("/me/queue", response_model=JobQueueResponse)
def get_my_action_queue(
    cursor: Optional[str] = Query(None, description="Keyset cursor for pagination"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve jobs waiting for the caller's action. Enforces SoD, stage matching, and absence handover."""
    predicate = compile_my_queue_predicate(db, caller)
    query = db.query(Job).filter(predicate)

    # Compute count from the exact same predicate
    total_count = query.count()
    items, next_cursor = paginate_jobs_query(query, cursor=cursor, limit=limit)

    return JobQueueResponse(
        count=total_count,
        items=[JobResponse.model_validate(j) for j in items],
        next_cursor=next_cursor,
    )
