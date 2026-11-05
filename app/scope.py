"""SQL Scope Compiler for high-performance job listing and queue filtering.

Compiles user active grants and SoD constraints into optimized SQL WHERE predicates:
- Handles wildcard dimensional matching (NULL = all)
- Explicit DENY grants unconditionally override ALLOW grants
- Separation of duties (Maker != Checker)
- Absentee handover (jobs assigned to absent staff return to pool)
- Keyset pagination (updated_at, id)
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, not_, true, false, desc
from sqlalchemy.sql.elements import BinaryExpression

from app.clock import get_now
from app.models import User, Job, Grant, RolePermission
from app.permissions import JOB_VIEW, JOB_PREPARE, JOB_CHECK, JOB_FILE


def _grant_to_job_scope_condition(grant: Grant) -> Any:
    """Translate a single Grant row into a SQLAlchemy Job predicate."""
    clauses = []
    if grant.client_id is not None:
        clauses.append(Job.client_id == grant.client_id)
    if grant.branch_id is not None:
        clauses.append(Job.branch_id == grant.branch_id)
    if grant.direction is not None:
        clauses.append(Job.direction == grant.direction)
    if grant.mode is not None:
        clauses.append(Job.mode == grant.mode)

    if not clauses:
        return true()
    return and_(*clauses) if len(clauses) > 1 else clauses[0]


def compile_permission_scope(
    db: Session,
    user: User,
    permission: str,
    at: Optional[datetime] = None,
) -> Any:
    """Compile a user's active grants for a specific permission into an optimized SQL predicate."""
    eval_time = at or get_now()
    if eval_time.tzinfo is None:
        eval_time = eval_time.replace(tzinfo=timezone.utc)
    else:
        eval_time = eval_time.astimezone(timezone.utc)

    # If user is absent and permission is not view, user has no active rights
    if user.status == "absent" and permission != JOB_VIEW:
        return false()

    # Query active grants where role holds the requested permission as of eval_time
    active_grants = (
        db.query(Grant)
        .join(
            RolePermission,
            and_(
                RolePermission.role_id == Grant.role_id,
                RolePermission.permission == permission,
                RolePermission.added_at <= eval_time,
                or_(RolePermission.removed_at.is_(None), RolePermission.removed_at > eval_time),
            ),
        )
        .filter(
            Grant.user_id == user.id,
            Grant.created_at <= eval_time,
            Grant.valid_from <= eval_time,
            or_(Grant.valid_to.is_(None), Grant.valid_to >= eval_time),
            or_(Grant.revoked_at.is_(None), Grant.revoked_at > eval_time),
            or_(
                Grant.cover_for_user_id.is_(None),
                Grant.cover_for_user_id.in_(
                    db.query(User.id).filter(User.status == "absent").scalar_subquery()
                ),
            ),
        )
        .all()
    )

    if not active_grants:
        return false()

    allow_conditions = []
    deny_conditions = []

    for g in active_grants:
        cond = _grant_to_job_scope_condition(g)
        if g.effect == "deny":
            deny_conditions.append(cond)
        else:
            allow_conditions.append(cond)

    if not allow_conditions:
        return false()

    allow_clause = or_(*allow_conditions) if len(allow_conditions) > 1 else allow_conditions[0]

    if deny_conditions:
        deny_clause = or_(*deny_conditions) if len(deny_conditions) > 1 else deny_conditions[0]
        return and_(allow_clause, not_(deny_clause))

    return allow_clause


def compile_jobs_view_predicate(
    db: Session,
    user: User,
    at: Optional[datetime] = None,
) -> Any:
    """Compile SQL predicate for GET /jobs (jobs visible to user)."""
    scope_pred = compile_permission_scope(db, user, JOB_VIEW, at)

    # Client users are strictly constrained to their own organization's client_id
    if user.type == "client":
        if not user.client_id:
            return false()
        return and_(Job.client_id == user.client_id, scope_pred)

    return scope_pred


def compile_my_queue_predicate(
    db: Session,
    user: User,
    at: Optional[datetime] = None,
) -> Any:
    """Compile SQL predicate for GET /me/queue (jobs waiting for user's action)."""
    if user.status == "absent":
        return false()

    eval_time = at or get_now()

    # Scope for pipeline stages
    prepare_scope = compile_permission_scope(db, user, JOB_PREPARE, eval_time)
    check_scope = compile_permission_scope(db, user, JOB_CHECK, eval_time)
    file_scope = compile_permission_scope(db, user, JOB_FILE, eval_time)

    stage_clauses = []

    # Stage: CONFIRMED or REOPENED -> action: prepare
    stage_clauses.append(and_(Job.stage.in_(["CONFIRMED", "REOPENED"]), prepare_scope))

    # Stage: PREPARED -> action: check with SoD (maker != checker)
    stage_clauses.append(
        and_(
            Job.stage == "PREPARED",
            check_scope,
            or_(Job.prepared_by.is_(None), Job.prepared_by != user.id),
        )
    )

    # Stage: CHECKED -> action: file
    stage_clauses.append(and_(Job.stage == "CHECKED", file_scope))

    action_ready_clause = or_(*stage_clauses)

    # Assignment condition: unassigned OR assigned to me OR assignee is absent
    absent_user_subquery = db.query(User.id).filter(User.status == "absent").scalar_subquery()
    assignee_clause = or_(
        Job.assigned_to.is_(None),
        Job.assigned_to == user.id,
        Job.assigned_to.in_(absent_user_subquery),
    )

    return and_(action_ready_clause, assignee_clause)


def parse_cursor(cursor_str: Optional[str]) -> Optional[Tuple[datetime, str]]:
    """Parse keyset cursor format 'YYYY-MM-DDTHH:MM:SS.mmmmmm+00:00|JOB_ID'."""
    if not cursor_str:
        return None
    try:
        ts_part, job_id = cursor_str.split("|", 1)
        # Handle unencoded '+' that query string decoders convert to space
        if " " in ts_part and "+" not in ts_part:
            parts = ts_part.rsplit(" ", 1)
            ts_part = "+".join(parts)
        dt = datetime.fromisoformat(ts_part)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt, job_id
    except Exception:
        return None


def format_cursor(job: Job) -> str:
    """Encode keyset cursor from Job row."""
    dt = job.updated_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return f"{dt.isoformat()}|{job.id}"


def paginate_jobs_query(
    query,
    cursor: Optional[str] = None,
    limit: int = 50,
):
    """Apply keyset pagination over (updated_at DESC, id DESC)."""
    parsed = parse_cursor(cursor)
    if parsed:
        c_dt, c_id = parsed
        query = query.filter(
            or_(
                Job.updated_at < c_dt,
                and_(Job.updated_at == c_dt, Job.id < c_id),
            )
        )

    items = query.order_by(desc(Job.updated_at), desc(Job.id)).limit(limit + 1).all()

    next_cursor = None
    if len(items) > limit:
        page_items = items[:limit]
        next_cursor = format_cursor(page_items[-1])
    else:
        page_items = items

    return page_items, next_cursor
