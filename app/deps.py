"""Common API dependencies: database sessions and caller authentication."""
from typing import Optional
from fastapi import Header, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id", description="User ID identifying caller"),
    db: Session = Depends(get_db),
) -> User:
    """Resolve caller user model from X-User-Id header."""
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header 'X-User-Id' is required for authentication",
        )
    user = db.query(User).filter(User.id == x_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User '{x_user_id}' not found in directory",
        )
    return user


def get_actor_run_id(
    x_run_id: Optional[str] = Header(None, alias="X-Run-Id", description="Batch run ID for system actors"),
) -> Optional[str]:
    """Extract optional parser batch run ID."""
    return x_run_id
