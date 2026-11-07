# System Design: Nagarkot Access Control Service

## 1. Domain Context & Problem
Nagarkot Forwarders Pvt. Ltd. is a licensed customs brokerage (~120 staff, 5 branches) clearing air and sea shipments. Altering a filed shipping bill or bill of entry triggers statutory fines, cargo impoundment, and license suspension under the Indian Customs Act.

Following an incident where a filed job was improperly altered, this service acts as the policy decision engine answering: **who may do what on which job, why, and who could have done so historically?** It enforces separation of duties, fail-closed zero trust, and compiles access policies directly into SQL.

---

## 2. Domain Model & Key Concepts
- **Jobs**: Shipments defined by Client, Branch, Direction (`IMPORT`/`EXPORT`), and Mode (`AIR`/`FCL`/`LCL`). Lifecycle: `CONFIRMED` -> `PREPARED` -> `CHECKED` -> `FILED`, plus `CANCELLED` and `REOPENED`. Each reopen increments `cycle`, isolating audit accountability.
- **Assigned_to is a Soft Hint**: Routes work to personal queues, but never gates permissions. Qualified colleagues may act on unassigned jobs or cover for absent peers.
- **Grants & NULL Wildcards**: Binds user to role over a 4D scope: `(client_id, branch_id, direction, mode)`. `NULL` acts as a wildcard (`ALL`), enabling concise declarations without combinatorial rows. Append-only with `valid_from`, `valid_to`, `revoked_at`.
- **Roles as Data, Permissions in Code**: Permissions are fixed code constants (`app/permissions.py`). Roles and role-permission mappings are versioned database rows (`added_at`, `removed_at`), allowing runtime adjustments without code deployment.

---

## 3. Explicit Architectural Trade-Offs
1. **Roles as Data vs. Code**: Versioned database rows enable runtime role creation while preserving historical audit accuracy without software deployments.
2. **NULL Wildcards vs. Cross-Product Scopes**: `NULL` wildcards keep user profiles minimal (~1–5 rows) instead of 15,000-row combinatorial cross-products per user across dimensions.
3. **Deny-Wins vs. Specificity Scoring**: Specificity scoring introduces brittle precedence rules. Absolute **Deny-Wins** ensures any active matching deny grant unconditionally blocks access.
4. **Compile-to-SQL vs. In-Memory Python Filtering**: Ingesting 200,000 jobs into Python exhausts RAM. Compiling rules into SQL `WHERE` clauses offloads filtering to SQLite B-tree indexes, ensuring fast keyset pagination.
5. **Zero Decision Caching vs. Redis**: Redis caching introduces stale authorization windows for revoked staff. Direct indexed SQL executes in milliseconds; zero caching guarantees instant revocation.

---

## 4. The 8-Stage Decision Pipeline
Every evaluation (`decide()`) executes an 8-stage deterministic pipeline:
1. `USER_KNOWN`: Caller exists and user type is valid (client users blocked from operational mutations).
2. `USER_ACTIVE`: Absent staff cannot perform mutations (read access preserved).
3. `JOB_DATA_COMPLETE`: Shipment attributes and stages are complete.
4. `ACTION_KNOWN`: Action exists in the permission catalogue.
5. `STAGE_VALID`: Action matches lifecycle stage (e.g. cannot check a FILED job).
6. `GRANT_COVERS_SCOPE`: Caller holds an active allow grant covering scope with no overriding deny.
7. `SOD_OK`: Four-eyes checks (Maker cannot Check own preparation; Requester cannot approve own action).
8. `REASON_PROVIDED`: Mandatory justification supplied for overrides or sensitive requests.

---

## 5. Answers to the 14 Standard Questions

### Q1: Should everyone see everything? Who sees what vs who may act?
No. Visibility (`job.view`) is decoupled from operational agency. SQL predicate `compile_jobs_view_predicate()` filters staff by their branch/client grants and restricts client users strictly to their `client_id`, redacting internal notes and staff handlers. Operational actions require separate matching operational grants.

### Q2: How to describe someone who is Maker for every client but Checker for only a few? Someone who is Checker for one client at one branch, imports only?
Through dimensional grants. A national Maker with narrow Checker access holds one wildcard Maker grant `(client=ALL, branch=ALL, dir=ALL, mode=ALL)` and targeted Checker grants for specific clients (C03, C05). A restricted officer (Rohit Mehta) holds one grant: `checker, client=C01, branch=BR-MUM, direction=IMPORT, mode=ALL`. Outside shipments fail with `NO_GRANT`.

### Q3: Person who prepared a checklist is also qualified to approve it?
Qualification does not grant authorization on a specific shipment. Even if an officer holds both Maker and Checker roles (e.g. Karan Shah), runtime Separation of Duties (SoD) enforces `job.prepared_by != caller.id` for the current cycle. If the preparer attempts to check, access is denied with `SOD_VIOLATION_MAKER_CHECKER`.

### Q4: Person responsible for a job is absent?
Marking a user absent immediately suspends operational rights while preserving read-only view. In-flight jobs assigned to them are unassigned and returned to the branch pool. Absence coverage is granted via time-bounded grants specifying `cover_for_user_id` and `valid_to` (e.g. Pooja Sharma covering Delhi for Imran Shaikh). The engine dynamically checks that the covered person is currently absent; if they return to work, the cover grant becomes inactive immediately.

### Q5: Jobs a person is halfway through when their responsibilities change?
When a grant is revoked or a role's permissions are removed (`PUT /roles/{id}/permissions`), the service sweeps in-flight jobs via `auto_unassign_ineligible_jobs()`. If the user no longer holds permission for the next required action, the job is unassigned (`assigned_to = NULL`), audited, and returned to the branch queue. For temporal grant expirations without active revocation events, an administrative sweep endpoint (`POST /grants/sweep-expired`) performs scheduled cleanup; in production, this would be wired to a periodic background task.

### Q6: Who can cancel a filed job or reopen a closed one, and what should it take?
Filed shipments represent legal customs declarations and cannot be modified directly. Cancelling a filed job or reopening a closed one mandates a two-person rule: an authorized user submits a request with mandatory reason, creating a pending approval. A distinct Compliance Approver (`job.approve_sensitive`) must review and approve it; self-approval is blocked.

### Q7: A client's own employee needs to follow their shipments?
Client employees are registered with `type = 'client'`, mandatory `client_id`, and role `Client Viewer` (`job.view`). The engine blocks operational actions (`CLIENT_USER_RESTRICTED`), SQL queries enforce `Job.client_id == user.client_id`, and serializers strip internal notes, assigned handlers, and staff identities. Furthermore, `GET /users` requires authentication; client users only see their own profile to prevent directory enumeration, while the UI relies on a staff bootstrap persona to populate the user switcher.

### Q8: Admin needs to fix a stuck job? Admin tries to make themselves more powerful?
Ops Admins hold `job.override`, allowing `override_send_back` or reassignment with mandatory logged justification; they cannot bypass SoD or alter FILED jobs. Self-escalation is prevented because users cannot grant/revoke roles for themselves, cannot edit permissions of roles they hold, cannot grant scopes broader than their own, and cannot grant privileged roles without `access.manage_privileged`.

### Q9: Automated parser that creates/updates jobs overnight?
The EDI parser is a `system` user with role `Parser` (`job.create`, `job.update_unfiled`). It cannot advance workflow stages and can only update unfiled `CONFIRMED` jobs on allow-listed fields (`internal_notes`, `assigned_to`). Each run passes `X-Run-Id`, recorded in `audit_log.actor_run_id` for automated traceability.

### Q10: How to answer "why can she do this and he can't?"
Via `GET /explain/compare?users=priya,faisal&action=check&job_id=JOB-05`. The endpoint evaluates both users through the identical 8-stage pipeline, compares matched grants and failure reason codes, and returns a side-by-side explanation (e.g. Priya holds an active Checker grant for Mumbai, whereas Faisal holds only read-only Viewer access).

### Q11: How to answer "who could have changed this job on the 3rd?"
Via `GET /jobs/{id}/who-could?action=prepare&at=2026-10-03T14:00:00Z`. The engine reconstructs system state at timestamp T from historical grants, versioned role permissions, absence history, and audit log stage replays. It evaluates every directory user against that historical snapshot and correlates eligible users with the actual recorded actor.

### Q12: How to introduce a new kind of role next quarter while engineering is busy?
Because roles are data, an administrator with `roles.manage` creates a new role via `POST /roles` and assigns permissions via `PUT /roles/{id}/permissions` using the existing catalogue. The role takes effect immediately across all endpoints without code changes, deployments, or database migrations.

### Q13: How to make a person's "jobs waiting for me" count match what they can actually do?
By compiling identical decision logic into SQL predicates (`compile_my_queue_predicate()`). The endpoint translates active allow/deny grants, stage requirements, SoD constraints (`prepared_by != me`), and absentee assignment rules into a single SQL query. Both `COUNT(*)` and keyset pagination execute over this exact predicate, ensuring reported counts match actionable shipments.

### Q14: What happens when the system is unsure?
The service fails closed (zero trust). If an action is uncatalogued, user unknown, job data malformed, or an unexpected exception occurs, the engine logs an audit event with decision `DENY` and reason `INDETERMINATE`. Ambiguous states never resolve to permissive access.

---

## 6. Answers to Three Added Architecture Questions

### Q15: How to prevent locking out the organization when revoking or demoting administrators?
The system enforces a **Last-Admin Lock-Out Guard** in `revoke_grant()` and role demotions. Before revoking a `super_admin` grant, the service counts active Super Admins. If the target is the sole remaining active administrator, the transaction aborts with HTTP 403 Forbidden (`LOCKOUT_PREVENTED`), preventing administrative lockout.

### Q16: How to handle client or branch corrections on miscreated jobs?
Altering client or branch on an in-flight job could bypass jurisdiction and confidentiality. Corrections are permitted only during `CONFIRMED` stage via `job.update_unfiled`. Once in `PREPARED` or beyond, client and branch are immutable; corrections require Ops Admin rollback (`override_send_back`) with justification or formal cancellation and re-creation.

### Q17: Who can view audit logs and how is audit log integrity guaranteed?
Audit log access requires permission `audit.view`. Serializers redact security internals for non-supervisors. SQLite triggers unconditionally abort `UPDATE` and `DELETE` queries on `audit_log`, guaranteeing database-level immutability against application exploits and database administrators.

---

## 7. Assumptions & Cut Scope

### Assumptions:
1. **Authentication Gateway**: Authentication is delegated to an external gateway supplying `X-User-Id` (and optional `X-Run-Id`).
2. **Injectable Clock**: System time is centralized through `app/clock.py`, enabling deterministic testing and time-travel queries.
3. **UTC Everywhere**: All timestamps are timezone-aware ISO 8601 UTC strings.

### Cut Scope:
- **No In-Memory Cache**: Redis caching was omitted to eliminate stale permission windows and ensure immediate revocation.
- **No Custom Frontend**: Swagger UI at `/docs` serves as the testing and evaluation interface.
- **No Graph Engine**: Relational dimensional grants with `NULL` wildcards satisfy requirements without graph engine overhead.
