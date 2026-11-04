"""Approval management endpoints for sensitive operations on shipments."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User, Approval
from app.approvals import approve_request, reject_request
from app.schemas import ApprovalResponse, ApprovalDecisionRequest

router = APIRouter(tags=["Approvals & Governance"])


@router.get("/approvals", response_model=List[ApprovalResponse])
def list_approvals(
    status_filter: Optional[str] = Query("pending", alias="status", description="Filter by approval status"),
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pending approval requests requiring two-person authorization."""
    query = db.query(Approval)
    if status_filter:
        query = query.filter(Approval.status == status_filter)
    return query.order_by(Approval.created_at.desc()).all()


@router.post("/approvals/{id}/approve", response_model=ApprovalResponse)
def approve_sensitive_action(
    id: str,
    body: ApprovalDecisionRequest,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve a pending sensitive action (Approver must have job.approve_sensitive and differ from requester)."""
    return approve_request(db, approver=caller, approval_id=id, reason=body.reason)


@router.post("/approvals/{id}/reject", response_model=ApprovalResponse)
def reject_sensitive_action(
    id: str,
    body: ApprovalDecisionRequest,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject a pending sensitive action."""
    return reject_request(db, approver=caller, approval_id=id, reason=body.reason)
