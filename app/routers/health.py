"""Health check endpoint."""
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """Service health indicator."""
    return {"status": "ok", "service": "nagarkot-access-control"}
