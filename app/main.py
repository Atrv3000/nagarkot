"""FastAPI application initialization, router registration, and lifecycle events."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import (
    health,
    decide,
    jobs,
    me,
    approvals,
    grants,
    roles,
    users,
    audit,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schemas and immutability triggers on startup
    init_db()
    yield


app = FastAPI(
    title="Nagarkot Forwarders - Access Control Service",
    description=(
        "Production-grade Access Control Service for Nagarkot Forwarders Pvt. Ltd. "
        "Enforces deterministic 8-stage decision pipeline, multi-scope grants, "
        "separation of duties (SoD), two-person approval workflows, and immutable audit logs."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(decide.router)
app.include_router(jobs.router)
app.include_router(me.router)
app.include_router(approvals.router)
app.include_router(grants.router)
app.include_router(roles.router)
app.include_router(users.router)
app.include_router(audit.router)


@app.get("/", include_in_schema=False)
def root():
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Fail-closed global exception handler: ensures any unexpected crash produces safe 500."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error: unexpected indeterminate condition. Operation failed closed."},
    )
