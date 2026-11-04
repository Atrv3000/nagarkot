# Architecture & Implementation Plan: Nagarkot Access Control Service

## Context & Objectives
Nagarkot Forwarders Pvt. Ltd. is a customs brokerage (~120 staff, 5 branches). Following an incident where a filed shipment was altered improperly, this service implements a bulletproof, deterministic Access Control Engine and management layer deciding **who may do what on which job** (shipment).

Key characteristics:
1. **Zero-Trust & Fail-Closed**: Any anomaly, indeterminate state, unknown user, missing attribute, or engine exception resolves to `DENY` with audit logging.
2. **Explicit Deny Precedence**: Scope grants match along client, branch, direction, mode (NULL = wildcard). Deny grants unconditionally override allow grants.
3. **Data-Driven Roles & Temporal Versioning**: Roles and their permissions are rows in the database with temporal validity (`added_at`, `removed_at`), enabling exact reconstruction of decisions "as of" any historical timestamp $T$.
4. **Separation of Duties (SoD)**: Four-eyes principle enforced per job cycle (e.g. Maker cannot Check their own preparation; Requester cannot approve their own sensitive action).
5. **Two-Person Sensitive Actions**: Altering or reopening a FILED job requires a staged approval workflow (`NEEDS_APPROVAL` -> `Approver` approval).
6. **Dual Evaluation Paths with Perfect Equivalence**:
   - Python Engine (`app/decision.py`): Comprehensive 8-stage decision trace with full explanations.
   - SQL Compiler (`app/scope.py`): Compiles user grants and SoD rules into high-performance SQL predicates for `/me/queue` and `/jobs` pagination (p95 < 200ms at 200,000 jobs).
7. **Tamper-Evident Audit Logging**: SQLite database triggers forbid `UPDATE` and `DELETE` on the `audit_log` table.

---

## Phase Breakdown

### Phase 1: Project Skeleton, Schemas, Database & Core Domain Models
- `requirements.txt`: FastAPI, Uvicorn, SQLAlchemy 2.0, Pydantic v2, Pytest, HTTPX.
- `Makefile`: `setup`, `seed`, `run`, `test`, `scale`, `bench`, `demo`.
- `app/clock.py`: Thread-safe, injectable time provider (`get_now()`, `set_time()`, `reset_time()`).
- `app/permissions.py`: Fixed permission catalogue constants and privileged check utilities.
- `app/db.py`: SQLite engine with WAL mode, foreign keys pragma, trigger creation, session dependency.
- `app/models.py`: SQLAlchemy 2.0 models for `users`, `branches`, `clients`, `jobs`, `roles`, `role_permissions`, `grants`, `sod_rules`, `approvals`, `audit_log`.
- `app/schemas.py`: Pydantic request/response schemas.

### Phase 2: Decision Engine & Scope Compiler
- `app/decision.py`: `decide(user_id, action, job, at=now)`:
  - 8-stage precedence order (USER_KNOWN, USER_ACTIVE, JOB_DATA_COMPLETE, ACTION_KNOWN, STAGE_VALID, GRANT_COVERS_SCOPE, SOD_OK, REASON_PROVIDED).
  - Returns `Decision` with full explanation trace, matched grants, denying grants.
  - Historical "as of" replay using audit logs and temporal records.
  - Explain/compare helpers.
- `app/scope.py`: Compiles user's active grants into SQLAlchemy SQL expressions (Allow ORs, Deny NOT ORs, Stage matching, SoD predicates, Assignee absence checks).
- Tests: Unit tests for all 8 decision checks, SoD rules, Deny-override, time-travel decisions.

### Phase 3: Access Management, Job Workflows, Approvals & Audit Triggers
- `app/grants.py`: Multi-scope grant expansion, scope containment verification, self-grant prohibition, privileged grant restrictions, auto-unassigning in-flight jobs on revocation.
- `app/jobs.py`: State transition state machine (CONFIRMED -> PREPARED -> CHECKED -> FILED; CANCELLED, REOPENED).
- `app/approvals.py`: Two-person rule for sensitive actions, state freshness verification (fail-closed if job changed).
- `app/audit.py`: Append-only audit logger; DB triggers blocking UPDATE/DELETE.
- Fast-API Routers:
  - `routers/decide.py`: `/decide`, `/explain/compare`
  - `routers/jobs.py`: `/jobs`, `/jobs/{id}`, `/jobs/{id}/actions/{action}`, `/jobs/{id}/who-could`, `/jobs/{id}/history`
  - `routers/me.py`: `/me/queue`
  - `routers/approvals.py`: `/approvals`, `/approvals/{id}/approve`, `/approvals/{id}/reject`
  - `routers/grants.py`: `/grants`, `/grants/{id}/revoke`, `/users/{id}/grants`, `/users/{id}/access`
  - `routers/roles.py`: `/roles`, `/roles/{id}/permissions`
  - `routers/users.py`: `/users/{id}/status`
  - `routers/audit.py`: `/audit`
  - `routers/health.py`: `/health`

### Phase 4: Deterministic Seed Data Generator
- `scripts/seed.py`:
  - Deterministic PRNG (`seed=42`).
  - 5 Branches (Mumbai-Fort, Nhava Sheva, Delhi-ICD, Chennai, Kolkata).
  - 10 Clients (C01..C10).
  - 20 Users + Zoya Ansari (new joiner):
    - Asha Rao, Rohit Mehta, Neha Kulkarni, Imran Shaikh (absent), Pooja Sharma (7-day cover for Imran), Priya Nair, Karan Shah, Anita D'Souza, Tarun Das, Vikram Joshi, Sunita Patil, Deepak Verma, Meera Iyer, Om Agrawal, Faisal Khan, Lakshmi Iyer, Arjun Reddy, Rajesh Gupta, Sneha Kapoor, overnight-parser, Zoya Ansari.
  - ~300 Jobs across directions, modes, and stages with consistent historical backdated events (~30 days).
  - Showcase jobs with static refs (e.g. `NF-SHOWCASE-FILED`, `NF-SHOWCASE-PREPARED-SOD`, `NF-SHOWCASE-STUCK`).

### Phase 5: Verification & Comprehensive Test Suite
- Test suite covering:
  1. Maker/Checker conflict (SoD)
  2. Narrow-scope checker (branch/client/direction restrictions)
  3. Absent owner & cover grants (with expiration)
  4. Changed responsibility & auto-unassign
  5. Sensitive actions (cancel_filed, reopen, approval lifecycle, stale fail-closed)
  6. Admin self-escalation prevention & scope containment & last super-admin guard
  7. Admin override (cannot bypass SoD or touch FILED without approval)
  8. Overnight parser (system user, create/update_unfiled only, actor_run_id)
  9. Client user (only client's shipments, internal fields redacted)
  10. Deny grant absolute precedence
  11. Explain/compare parity
  12. Historical "as of" time-travel validation
  13. Fail-closed on corrupted data / engine exception
  14. SQL queue equivalence: Python decide() == SQL predicate for every seeded user
  15. Audit table trigger protection (UPDATE/DELETE raised error)
  16. Dynamic role creation via API taking immediate effect without code changes

### Phase 6: Scale Generator & Benchmark Engine
- `scripts/generate_scale.py`: Efficient bulk generation of 500 users and 200,000 jobs with realistic grant distributions and proper B-tree index layout.
- `scripts/benchmark.py`: Measures p50, p95, p99 latencies for `/me/queue` and `/jobs` first page keyset queries against the 200k job database.

### Phase 7: Documentation, Demo Script & Access Inspection
- `scripts/describe_access.py`: Prints plain-English matrix of each user's effective permissions.
- `docs/DEMO_SCRIPT.md` & `scripts/demo.sh`: 5-minute executable walkthrough.
- `DESIGN.md`: Detailed architecture design answering Q1-Q14 + 3 extra deep-dive questions.
- `LEARNING_GUIDE.md`: Code walkthrough & 25 interview questions with model answers.
- `README.md`: Quickstart, user matrix, showcase refs, curl cheat sheet, benchmark results.

### Phase 8: Final Validation & Submission
- Fresh execution, tests, scale run, benchmark capture into README, final git log inspection.
