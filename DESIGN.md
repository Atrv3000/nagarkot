# System Design: Nagarkot Access Control Service

## 1. Domain Context & Problem
Nagarkot Forwarders Pvt. Ltd. is a licensed customs brokerage (~120 staff, 5 branches: Mumbai-Fort, Nhava Sheva, Delhi-ICD, Chennai, Kolkata) clearing air and sea shipments (FCL/LCL). In customs clearance, unauthorized alteration of a filed shipping bill or bill of entry triggers statutory fines, cargo impoundment, and license suspension under the Indian Customs Act.

Following an incident where a filed job was altered without authorization or clear ownership, this service provides an authoritative policy decision engine answering: **who may do what on which job, why, and who could have done so historically?** It enforces separation of duties, fail-closed zero-trust evaluation, and compiles policies directly into SQL for high-volume operational queues.

---

## 2. Domain Model & Key Concepts
- **Jobs**: Shipments defined by four dimensions: Client, Branch, Direction (`IMPORT`, `EXPORT`), and Mode (`AIR`, `FCL`, `LCL`). Jobs progress sequentially: `CONFIRMED` -> `PREPARED` -> `CHECKED` -> `FILED`, with terminal stage `CANCELLED` and exceptional stage `REOPENED`. Every reopening increments a `cycle` counter, isolating audit accountability across workflow iterations.
- **Assigned_to is a Soft Hint**: `assigned_to` routes work to personal queues, but never gates permissions. Qualified colleagues within scope may act on unassigned jobs or cover for absent peers.
- **Grants & NULL Wildcards**: Grants bind a user to a role over a 4D scope: `(client_id, branch_id, direction, mode)`. `NULL` acts as a universal wildcard (`ALL`), enabling concise grants without combinatorial rows. Grants are append-only with `valid_from`, `valid_to`, and `revoked_at`.
- **Roles as Data, Permissions in Code**: Permissions are fixed code constants (`app/permissions.py`) guarding endpoints. Roles are mutable database records (`roles`, `role_permissions`) with versioned membership (`added_at`, `removed_at`), allowing runtime role adjustments without code deployment.

---

## 3. Explicit Architectural Trade-Offs
1. **Roles as Data vs. Code**: Hardcoded role enums require software deployments for organizational changes. Versioned database rows enable runtime administrative role creation while preserving historical audit accuracy.
2. **NULL Wildcards vs. Cross-Product Scopes**: Expanding national grants across all dimensions would generate 15,000 rows per user. Universal wildcards (`NULL`) keep profiles minimal (~1–5 rows), avoiding index bloat.
3. **Deny-Wins vs. Specificity Scoring**: Specificity scoring introduces brittle precedence rules. We enforce absolute **Deny-Wins**: if any active matching grant has `effect = deny`, access is unconditionally denied.
4. **Compile-to-SQL vs. Python In-Memory Filtering**: Ingesting 200,000 jobs into Python memory exhausts RAM and breaks pagination. Compiling decision rules into SQL `WHERE` clauses offloads filtering to SQLite B-tree indexes, ensuring fast keyset pagination matching single-job decisions.
5. **Zero Decision Caching vs. Redis**: Redis caching introduces stale authorization windows where revoked staff retain access until TTL expiry. Single-job SQL evaluations execute in milliseconds; omitting caching guarantees instant revocation without cache invalidation bugs.

---

## 4. The 8-Stage Decision Pipeline
Every evaluation (`decide()`) executes an 8-stage deterministic pipeline:
1. `USER_KNOWN`: Caller exists and user type is valid (client users blocked from operational mutations).
2. `USER_ACTIVE`: Absent staff cannot perform operational mutations (read access preserved).
3. `JOB_DATA_COMPLETE`: Shipment attributes and stages are complete and valid.
4. `ACTION_KNOWN`: Action exists in the permission catalogue.
5. `STAGE_VALID`: Action matches current lifecycle stage (e.g. cannot check a FILED job).
6. `GRANT_COVERS_SCOPE`: Caller holds an active allow grant covering the 4D scope with no overriding deny grant.
7. `SOD_OK`: Four-eyes checks (Maker cannot Check own preparation; Requester cannot approve own sensitive action).
8. `REASON_PROVIDED`: Mandatory justification supplied for overrides or sensitive requests.

---

## 5. Answers to the 14 Standard Questions

### Q1: Should everyone see everything? Who sees what vs who may act?
No. Visibility (`job.view`) is decoupled from operational agency. Visibility is enforced in SQL queries via `compile_jobs_view_predicate()`: staff see shipments within their branch or client grants, while client users see only their own `client_id` with internal notes, assigned handlers, and staff identities redacted. Operational actions require explicit matching operational grants.

### Q2: How to describe someone who is Maker for every client but Checker for only a few? Someone who is Checker for one client at one branch, imports only?
Through composable dimensional grants. A national Maker with narrow Checker access holds one wildcard Maker grant `(client=ALL, branch=ALL, dir=ALL, mode=ALL)` and targeted Checker grants for specific clients (e.g. C03, C05). A restricted officer (Rohit Mehta) holds a single grant: `role='checker', client='C01', branch='BR-MUM', direction='IMPORT', mode=ALL`. Actions outside that scope fail with `NO_GRANT`.

### Q3: Person who prepared a checklist is also qualified to approve it?
Qualification does not grant authorization on a specific shipment. Even if a user holds both Maker and Checker roles (e.g. Karan Shah), the engine enforces runtime Separation of Duties (SoD): `job.prepared_by != caller.id` for the current cycle. If the same user prepared the shipment, the check is denied with `SOD_VIOLATION_MAKER_CHECKER`. The four-eyes principle is non-negotiable.

### Q4: Person responsible for a job is absent?
When a worker is marked absent, operational rights are immediately suspended while read-only view is retained. In-flight jobs assigned to them are automatically unassigned and returned to the branch queue. Absence coverage is handled via time-bounded grants specifying `cover_for_user_id` and `valid_to` (e.g. Pooja Sharma covering Delhi for Imran Shaikh). Once `valid_to` lapses, cover access terminates automatically.

### Q5: Jobs a person is halfway through when their responsibilities change?
When a user's grant is revoked, `revoke_grant()` runs an atomic sweep (`auto_unassign_ineligible_jobs()`). It inspects in-flight jobs assigned to that user; if the user no longer holds permission for the job's next required action, the job is unassigned (`assigned_to = NULL`), an audit event is logged, and the shipment returns to the pool for eligible colleagues to pick up.

### Q6: Who can cancel a filed job or reopen a closed one, and what should it take?
Filed shipments represent legal declarations submitted to Indian Customs and cannot be altered directly. Cancelling a filed job or reopening a closed one requires a two-person rule: an authorized user submits a request with a mandatory reason, transitioning it to `NEEDS_APPROVAL`. A distinct Compliance Approver (`job.approve_sensitive`) must review and approve it; self-approval is blocked by SoD guards.

### Q7: A client's own employee needs to follow their shipments?
Client employees are registered with `type = 'client'` and a mandatory `client_id`. They receive the `Client Viewer` role (`job.view`). The decision engine strictly blocks them from operational mutations (`CLIENT_USER_RESTRICTED`), SQL queries enforce `Job.client_id == user.client_id`, and API responses strip internal notes, assigned handlers, and staff identities.

### Q8: Admin needs to fix a stuck job? Admin tries to make themselves more powerful?
Ops Admins hold `job.override`, allowing `override_send_back` or reassigning stuck shipments with mandatory justification, but cannot bypass SoD or alter FILED jobs. Self-escalation is prevented by multi-layer guards: users cannot grant or revoke roles for themselves, cannot alter permissions on roles they hold, cannot grant scopes broader than their own, and cannot grant privileged roles without `access.manage_privileged`.

### Q9: Automated parser that creates/updates jobs overnight?
The EDI parser is a `system` user holding the `Parser` role with permissions `job.create` and `job.update_unfiled`. It is strictly forbidden from advancing workflow stages (`prepare`, `check`, `file`). It can only update unfiled `CONFIRMED` jobs on allow-listed fields (`internal_notes`, `assigned_to`). Each automated run passes an `X-Run-Id` header, recorded in `audit_log.actor_run_id` for batch traceability.

### Q10: How to answer "why can she do this and he can't?"
Via `GET /explain/compare?users=priya,faisal&action=check&job_id=JOB-05`. The endpoint evaluates both users through the identical 8-stage decision pipeline, compares evaluated stages, matched grants, and failure reason codes, and generates a structured side-by-side breakdown explaining the exact differential (e.g. Priya holds an active Checker grant covering Mumbai, whereas Faisal holds only read-only Viewer access).

### Q11: How to answer "who could have changed this job on the 3rd?"
Via `GET /jobs/{id}/who-could?action=prepare&at=2026-10-03T14:00:00Z`. The engine reconstructs system state at timestamp T by evaluating historical grant validity, versioned role permissions (`added_at <= T < removed_at`), absence history, and the job's stage replayed from audit logs. It evaluates every directory user against that historical snapshot and correlates eligible users with the actual recorded actor.

### Q12: How to introduce a new kind of role next quarter while engineering is busy?
Because roles are data, an administrator holding `roles.manage` creates a new role via `POST /roles` and assigns permissions via `PUT /roles/{id}/permissions` using the existing permission catalogue. The new role takes effect immediately across all operational endpoints without modifying application code, restarting services, or executing database migrations.

### Q13: How to make a person's "jobs waiting for me" count match what they can actually do?
By compiling identical decision logic into SQL predicates (`compile_my_queue_predicate()`). The queue endpoint translates active allow and deny grants, stage requirements, SoD constraints (`prepared_by != me`), and absentee assignment rules directly into a single SQL query. Both the total count (`COUNT(*)`) and paginated items execute over this exact predicate, guaranteeing that reported counts match actionable shipments.

### Q14: What happens when the system is unsure?
The service fails closed (zero-trust). If an action is uncatalogued, user unknown, job data corrupted, or an unexpected internal exception occurs, the engine logs a structured audit event with decision `DENY` and reason `INDETERMINATE`. Permissive access is never granted under ambiguous or erroneous conditions.

---

## 6. Answers to Three Added Architecture Questions

### Q15: How to prevent locking out the organization when revoking or demoting administrators?
The system enforces a **Last-Admin Lock-Out Guard** inside `revoke_grant()` and role demotion handlers. Before revoking any `super_admin` grant, the service counts active Super Admin grants. If the target is the sole remaining active Super Admin, the transaction aborts with HTTP 403 Forbidden (`LOCKOUT_PREVENTED`), guaranteeing continuous administrative oversight.

### Q16: How to handle client or branch corrections on miscreated jobs?
Altering client or branch on an in-flight job could bypass jurisdiction and data confidentiality. The service allows corrections only during `CONFIRMED` stage via `job.update_unfiled`. Once in `PREPARED` or beyond, client/branch fields are immutable; corrections require an Ops Admin rollback (`override_send_back`) with mandatory justification or cancellation and re-creation.

### Q17: Who can view audit logs and how is audit log integrity guaranteed?
Audit log access requires permission `audit.view`. Responses redact sensitive security internals for non-supervisors. Database triggers abort `UPDATE` and `DELETE` queries on `audit_log`, guaranteeing immutability even against database administrators or application exploits.

---

## 7. Assumptions & Cut Scope

### Assumptions:
1. **Authentication Gateway**: Authentication is delegated to an external gateway supplying `X-User-Id` (and optional `X-Run-Id`).
2. **Injectable Clock**: System time is centralized through `app/clock.py`, enabling past time-travel queries and deterministic testing without changing server clocks.
3. **UTC Everywhere**: All timestamps are timezone-aware ISO 8601 UTC strings.

### Cut Scope:
- **No In-Memory Cache**: Redis caching was deliberately omitted to eliminate stale permission windows and ensure immediate revocation enforcement.
- **No Custom Frontend**: Swagger UI at `/docs` serves as the interactive testing and evaluation interface.
- **No Complex Graph Hierarchy**: Relational dimensional grants with `NULL` wildcards completely satisfy customs brokerage requirements without graph engine overhead.
