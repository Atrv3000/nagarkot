"""Pydantic v2 schemas for API requests and structured responses."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------
# User Schemas
# ---------------------------------------------------------
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    status: str
    client_id: Optional[str] = None
    created_at: datetime


class UserStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(active|absent)$", description="active or absent")
    reason: str = Field(..., min_length=3, description="Reason for status change")


# ---------------------------------------------------------
# Role Schemas
# ---------------------------------------------------------
class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    allowed_user_types: List[str]
    permissions: List[str] = []
    created_at: datetime


class RoleCreate(BaseModel):
    id: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=128)
    allowed_user_types: List[str]
    permissions: List[str] = []


class RolePermissionsUpdate(BaseModel):
    permissions: List[str]
    reason: str = Field(..., min_length=3)


# ---------------------------------------------------------
# Grant Schemas
# ---------------------------------------------------------
class GrantCreateItem(BaseModel):
    role_id: str
    client_id: Optional[str] = None
    branch_id: Optional[str] = None
    direction: Optional[str] = None
    mode: Optional[str] = None
    effect: str = Field(default="allow", pattern="^(allow|deny)$")
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    reason: str = Field(..., min_length=3)
    cover_for_user_id: Optional[str] = None


class GrantCreateRequest(BaseModel):
    user_id: str
    grants: List[GrantCreateItem] = Field(..., min_length=1)


class GrantRevokeRequest(BaseModel):
    reason: str = Field(..., min_length=3)


class GrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    role_id: str
    client_id: Optional[str] = None
    branch_id: Optional[str] = None
    direction: Optional[str] = None
    mode: Optional[str] = None
    effect: str
    valid_from: datetime
    valid_to: Optional[datetime] = None
    granted_by: str
    created_at: datetime
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    reason: str
    cover_for_user_id: Optional[str] = None
    batch_id: str


class UserAccessSummary(BaseModel):
    user_id: str
    name: str
    status: str
    user_type: str
    active_grants_count: int
    plain_english_rules: List[str]


# ---------------------------------------------------------
# Job Schemas
# ---------------------------------------------------------
class JobCreate(BaseModel):
    ref: str = Field(..., min_length=3)
    client_id: str
    branch_id: str
    direction: str = Field(..., pattern="^(IMPORT|EXPORT)$")
    mode: str = Field(..., pattern="^(AIR|FCL|LCL)$")
    assigned_to: Optional[str] = None
    internal_notes: Optional[str] = None


class JobPatch(BaseModel):
    assigned_to: Optional[str] = None
    internal_notes: Optional[str] = None


class JobActionRequest(BaseModel):
    reason: Optional[str] = None
    new_assignee_id: Optional[str] = None  # For reassign


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ref: str
    client_id: str
    branch_id: str
    direction: str
    mode: str
    stage: str
    cycle: int
    created_at: datetime
    updated_at: datetime

    # Internal operational fields (redacted for client users)
    assigned_to: Optional[str] = None
    prepared_by: Optional[str] = None
    checked_by: Optional[str] = None
    filed_by: Optional[str] = None
    internal_notes: Optional[str] = None


class JobQueueResponse(BaseModel):
    count: int
    items: List[JobResponse]
    next_cursor: Optional[str] = None


# ---------------------------------------------------------
# Decision Schemas
# ---------------------------------------------------------
class CheckDetail(BaseModel):
    code: str
    passed: bool
    detail: str


class DecisionResponse(BaseModel):
    allowed: bool
    outcome: str  # ALLOW | DENY | NEEDS_APPROVAL
    primary_reason: Optional[str] = None
    checks: List[CheckDetail] = []
    matched_grants: List[str] = []
    denying_grants: List[str] = []
    required_permission: Optional[str] = None
    evaluated_at: datetime


class CompareResponse(BaseModel):
    user_a_id: str
    user_b_id: str
    user_a_decision: DecisionResponse
    user_b_decision: DecisionResponse
    comparison_summary: str


class ActorWhoCould(BaseModel):
    user_id: str
    name: str
    user_type: str
    status: str
    grants_held: List[str]


class WhoCouldResponse(BaseModel):
    job_id: str
    action: str
    evaluated_at: datetime
    actors_who_could: List[ActorWhoCould]
    actual_actor: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------
# Approval Schemas
# ---------------------------------------------------------
class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    action: str
    requested_by: str
    reason: str
    status: str
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime


class ApprovalDecisionRequest(BaseModel):
    reason: str = Field(..., min_length=3)


# ---------------------------------------------------------
# Audit Schemas
# ---------------------------------------------------------
class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    actor_id: str
    actor_type: str
    actor_run_id: Optional[str] = None
    event_type: str
    job_id: Optional[str] = None
    target_user_id: Optional[str] = None
    action: str
    decision: str
    reason_codes: List[str] = []
    grant_ids_used: List[str] = []
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    is_override: bool
