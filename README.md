# Nagarkot Forwarders - Access Control Service (ACS)

> **Access Control & Policy Decision Service for Nagarkot Forwarders Pvt. Ltd.**  
> Built with FastAPI, SQLAlchemy 2.0, SQLite WAL, and deterministic zero-trust authorization.

---

## 1. What It Is
Nagarkot Forwarders Pvt. Ltd. is a licensed customs brokerage (~120 staff, 5 branches) handling thousands of import and export shipments across air and sea freight. Following an incident where a filed customs entry was improperly altered, this service acts as the central policy decision engine answering: **who may do what on which job (shipment)?**

Key Capabilities:
- **8-Stage Deterministic Decision Pipeline**: Strict check evaluation with clear precedence and full explanation traces.
- **Multidimensional Scopes & Explicit Deny Override**: Access mapped across Client, Branch, Direction (Import/Export), and Mode (Air/FCL/LCL). Deny grants unconditionally override allow grants.
- **Four-Eyes Principle (Separation of Duties)**: Maker cannot Check their own preparation in the current cycle; Requester cannot approve their own sensitive action.
- **Two-Person Rule on FILED Shipments**: Once filed with Customs, a shipment cannot be modified or cancelled directly. Sensitive actions mandate approval by an authorized `Approver`.
- **High-Performance SQL Compilation**: Python decision logic compiles directly into optimized SQL predicates for `/me/queue` and `/jobs` pagination, evaluated against a 200,000-job scale database.
- **Immutable Append-Only Audit Logging**: SQLite relational triggers block `UPDATE` and `DELETE` at the database engine level.

---

## 2. 5-Step Quickstart

If you unzipped the submission archive into a clean directory:

### Step 1: Navigate and Set Up Virtual Environment

**Using Make (Linux / macOS):**
```bash
cd nagarkot  # or cd nagarkot-main depending on directory name
make setup
```

**Without Make (Windows PowerShell):**
```powershell
cd nagarkot  # or cd nagarkot-main
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Without Make (Linux / macOS / Git Bash):**
```bash
cd nagarkot  # or cd nagarkot-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Seed the Deterministic Dataset

**Using Make:**
```bash
make seed
```

**Without Make (PowerShell or Bash):**
```bash
python scripts/seed.py
```
*(Populates 5 branches, 10 clients, 21 personas, showcase jobs 01–08, and 300 shipments with 30-day history using seed=42)*

### Step 3: Run the Test Suite

**Using Make:**
```bash
make test
```

**Without Make (PowerShell or Bash):**
```bash
pytest -q
```
*(Runs pytest across all 68 tests in isolated in-memory DBs, including queue SQL-Python equivalence, access description integrity, scale smoke testing, and fail-closed guards)*

### Step 4: Run the Benchmark (200,000 Jobs, 500 Users)

**Using Make:**
```bash
make scale
make bench
```

**Without Make (PowerShell or Bash):**
```bash
python scripts/generate_scale.py --users 500 --jobs 200000 --db sqlite:///./scale.db
python scripts/benchmark.py --db sqlite:///./scale.db --iterations 100
```
*(Generates 200,000 shipments across 500 users into `scale.db` without wiping `nagarkot.db`, then measures p50/p90/p95/p99 query latencies across 100 iterations per scenario)*

### Step 5: Start the API Server

**Using Make:**
```bash
make run
```

**Without Make (PowerShell or Bash):**
```bash
uvicorn app.main:app --reload --port 8000
```
Open interactive Swagger UI at: **http://127.0.0.1:8000/docs**

---

## 3. Directory Personas & Plain-English Access Matrix

| # | Persona | Type / Status | Role(s) | Plain-English Scope & Governance Rules |
| :---: | :--- | :--- | :--- | :--- |
| **01** | **Asha Rao** | Staff / Active | Maker, Checker | Maker across **all** clients, branches, directions, and modes. Designated Checker for clients **C03, C05, and C07** only. Bound by SoD (cannot check shipments she prepared). |
| **02** | **Rohit Mehta** | Staff / Active | Checker | Restricted Checker for client **C01**, branch **Mumbai-Fort**, **IMPORT** only, all modes. Blocked on exports and other branches. |
| **03** | **Neha Kulkarni** | Staff / Active | Filer | Customs Filer for **Mumbai-Fort** and **Nhava Sheva** across all clients. |
| **04** | **Imran Shaikh** | Staff / **Absent** | Maker | Maker for **Delhi-ICD**. Currently marked **ABSENT** (operational rights suspended; read view retained; in-flight jobs returned to pool). |
| **05** | **Pooja Sharma** | Staff / Active | Checker, Maker (Cover) | Checker everywhere, plus active **7-day temporary cover grant** as Maker for **Delhi-ICD** covering Imran Shaikh. |
| **06** | **Priya Nair** | Staff / Active | Checker | Senior Checker across all clients, branches, directions, and modes. |
| **07** | **Karan Shah** | Staff / Active | Maker, Checker | Holds both Maker and Checker roles for client **C02** at **Chennai**. Enforced by runtime SoD per job cycle. |
| **08** | **Anita D'Souza** | Staff / Active | Maker | Specialized Maker for **EXPORT** shipments via **AIR** mode only. |
| **09** | **Tarun Das** | Staff / Active | Maker | Maker at **Kolkata** with an explicit **DENY** grant for client **C04** (recusal due to conflict of interest). |
| **10** | **Vikram Joshi** | Staff / Active | Supervisor | Operations Supervisor at **Mumbai-Fort** (can reassign unfiled jobs and cancel unfiled jobs). |
| **11** | **Sunita Patil** | Staff / Active | Approver | Head of Compliance. Authorized to approve sensitive actions (`cancel_filed`, `reopen`) across all scopes. |
| **12** | **Deepak Verma** | Staff / Active | Access Admin | Access Administrator scoped to **Mumbai-Fort** and **Nhava Sheva**. Cannot grant privileged roles. |
| **13** | **Meera Iyer** | Staff / Active | Ops Admin | Central Operations Admin. Can reassign jobs and issue `override_send_back` on stuck unfiled shipments with mandatory reason. |
| **14** | **Om Agrawal** | Staff / Active | Super Admin | Founding Super Administrator. Holds `access.manage_privileged` and `roles.manage`. Protected by last-admin lock-out guard. |
| **15** | **Faisal Khan** | Staff / Active | Viewer | General viewer across all scopes. Read-only access; cannot execute operational mutations. |
| **16** | **Lakshmi Iyer** | Staff / Active | Filer | Customs Filer for **Chennai** and **Kolkata** ports. |
| **17** | **Arjun Reddy** | Staff / Active | Checker (Revoked) | Checker grant for client **C08** was revoked yesterday; in-flight jobs were automatically unassigned and returned to the pool. |
| **18** | **Rajesh Gupta** | Client / Active | Client Viewer | Client user representing **C01 (Apex Global Traders)**. Can only see C01 shipments; internal operational notes/staff are redacted. |
| **19** | **Sneha Kapoor** | Client / Active | Client Viewer | Client user representing **C06 (Future Tech Electronics)**. Restricted strictly to C06 shipments. |
| **20** | **overnight-parser** | System / Active | Parser | Automated EDI ingestion service. Can create jobs and update unfiled CONFIRMED jobs. Cannot advance workflow stages. |
| **21** | **Zoya Ansari** | Staff / Active | *(None)* | New joiner with zero grants assigned. Zero-trust default: all actions denied. |

---

## 4. Showcase Job References

Use these fixed jobs in Swagger (`/docs`) or curl to verify specific features:

| Job Ref | Job ID | Client / Branch / Dir / Mode | Current Stage | Showcase Feature |
| :--- | :--- | :--- | :---: | :--- |
| `NF-SHOWCASE-FILED` | `JOB-SHOWCASE-01` | C01 / Mumbai-Fort / IMPORT / AIR | `FILED` | **Two-Person Rule**: Calling `cancel_filed` returns `NEEDS_APPROVAL`. Sunita Patil can approve via `/approvals/{id}/approve`. |
| `NF-SHOWCASE-PREPARED-SOD` | `JOB-SHOWCASE-02` | C03 / Mumbai-Fort / IMPORT / AIR | `PREPARED` | **Separation of Duties (SoD)**: Prepared by Asha Rao. Asha holds Checker for C03, but is denied check due to `SOD_VIOLATION_MAKER_CHECKER`. Priya Nair can check it. |
| `NF-SHOWCASE-STUCK` | `JOB-SHOWCASE-03` | C05 / Delhi-ICD / IMPORT / FCL | `PREPARED` | **Ops Admin Override**: Prepared by absent user Imran Shaikh. Meera Iyer can roll back to `CONFIRMED` via `override_send_back` with reason. |
| `NF-SHOWCASE-ARJUN-REVOKED` | `JOB-SHOWCASE-04` | C08 / Mumbai-Fort / IMPORT / AIR | `PREPARED` | **Auto-Unassignment**: Was assigned to Arjun Reddy; auto-unassigned and returned to pool when his grant was revoked yesterday. |
| `NF-SHOWCASE-ROHIT-CHECK` | `JOB-SHOWCASE-05` | C01 / Mumbai-Fort / IMPORT / AIR | `PREPARED` | **Restricted Scope Match**: Prepared by Asha Rao. Rohit Mehta is ALLOWED to check it; appears in Rohit's `/me/queue`. |
| `NF-SHOWCASE-ROHIT-EXPORT` | `JOB-SHOWCASE-06` | C01 / Mumbai-Fort / EXPORT / AIR | `PREPARED` | **Direction Gate**: Rohit Mehta is DENIED check (`primary_reason: NO_GRANT`; failing check `GRANT_COVERS_SCOPE` because grant is IMPORT only). |
| `NF-SHOWCASE-ROHIT-OTHER-BRANCH` | `JOB-SHOWCASE-07` | C01 / Nhava Sheva / IMPORT / AIR | `PREPARED` | **Branch Gate**: Rohit Mehta is DENIED check (`primary_reason: NO_GRANT`; failing check `GRANT_COVERS_SCOPE` because grant is Mumbai-Fort only). |
| `NF-SHOWCASE-DELHI-COVER` | `JOB-SHOWCASE-08` | C05 / Delhi-ICD / IMPORT / FCL | `CONFIRMED` | **Absence Delegation**: Actionable by Pooja Sharma under her temporary cover grant covering absent Imran Shaikh. |
| `NF-IMP-AIR-OCT03` | `JOB-HIST-DEMO-01` | C01 / Mumbai-Fort / IMPORT / AIR | `FILED` | **Historical Time-Travel**: Historical shipment with backdated events from 30+ days ago to answer *"Who could have changed this on Oct 3rd?"*. |

---

## 5. Performance Benchmark Results (200,000 Jobs, 500 Users)

The brief sets an SLA target of **p95 < 200 ms** across 200,000 jobs.

Tested against a freshly generated `scale.db` (200,000 shipments, 500 users) across 100 iterations per scenario without in-memory result caching:

| Scenario | Min (ms) | Mean (ms) | p50 (ms) | p90 (ms) | p95 (ms) | Target SLA | Result |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **GET /me/queue** (Asha Rao - National Maker) | 103 | 134 | 133 | 158 | **172** | < 200 ms | **PASS** |
| **GET /me/queue** (Rohit Mehta - Restricted Checker) | 98 | 118 | 115 | 145 | **152** | < 200 ms | **PASS** |
| **GET /me/queue** (Pooja Sharma - Checker + Delhi Cover) | 99 | 116 | 116 | 130 | **142** | < 200 ms | **PASS** |
| **GET /me/queue** (Neha Kulkarni - Filer MUM & NS) | 52 | 67 | 65 | 81 | **86** | < 200 ms | **PASS** |
| **GET /jobs** (Asha Rao - Staff View First Page) | 25 | 32 | 33 | 39 | **48** | < 200 ms | **PASS** |
| **GET /jobs** (Rajesh Gupta - Client User C01 View) | 48 | 58 | 56 | 68 | **95** | < 200 ms | **PASS** |

*(Note: On systems with slower disk I/O, latencies for sparse intersection queries like Rohit and Rajesh may take longer due to SQLite single-file page seeks. On typical SSD/NVMe developer environments, all six scenarios comfortably achieve p95 < 200 ms).*

### Technical Diagnosis: Why is Rohit's Queue Query Slower than Asha's?
- **Dataset Selectivity (~0.16% match)**: Rohit's Checker grant restricts access to `client = C01`, `branch = BR-MUM`, `direction = IMPORT`. In a uniform 200,000-job database, only ~330 jobs match this 4D intersection. By comparison, Asha matches national CONFIRMED/REOPENED jobs (tens of thousands of candidates).
- **Composite OR Predicate**: The queue query must evaluate dynamic assignee conditions (`assigned_to IS NULL OR assigned_to = :me OR assigned_to IN (SELECT id FROM users WHERE status = 'absent')`) and SoD four-eyes checks (`prepared_by IS NULL OR prepared_by != :me`).
- **Planner Trade-off on `ORDER BY updated_at DESC, id DESC LIMIT 50`**: SQLite's query planner faces a trade-off: if it uses the index on `(updated_at, id)` to avoid an in-memory sort, it must scan thousands of rows in updated order before finding 50 matching Rohit's sparse 4D criteria. If it uses the scope index `(stage, client_id, branch_id, direction)`, it must filter and sort the matching candidates.
- **Production Architecture**: In enterprise deployments, composite B-tree index scans or table partitioning (by client or branch) would streamline sparse intersection queries. Zero caching was chosen for this service to guarantee instant, zero-lag revocation security.

---

## 6. API Cheat Sheet & Curl Examples

All endpoints authenticate callers via the `X-User-Id` HTTP header.

### 1. Dry Run a Decision (Pure Read, No Audit Log)
```bash
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-05" \
  -H "X-User-Id: rohit-mehta" | python -m json.tool
```

### 2. Side-by-Side Explanation ("Why can she and he can't?")
```bash
curl -s -X GET "http://127.0.0.1:8000/explain/compare?users=priya-nair,faisal-khan&action=check&job_id=JOB-SHOWCASE-05" \
  -H "X-User-Id: om-agrawal" | python -m json.tool
```

### 3. Retrieve Personal Action Queue (`/me/queue`)
```bash
curl -s -X GET "http://127.0.0.1:8000/me/queue?limit=50" \
  -H "X-User-Id: asha-rao" | python -m json.tool
```

### 4. Advance Job Stage (Check a Shipment)
```bash
curl -s -X POST "http://127.0.0.1:8000/jobs/JOB-SHOWCASE-02/actions/check" \
  -H "X-User-Id: priya-nair" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 5. Request Cancellation on a FILED Shipment (Two-Person Rule)
```bash
curl -s -X POST "http://127.0.0.1:8000/jobs/JOB-SHOWCASE-01/actions/cancel_filed" \
  -H "X-User-Id: sunita-patil" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Client requested cancellation due to customs dock strike"}'
```

### 6. Historical Time-Travel ("Who could have changed this on Oct 3rd?")
```bash
curl -s -X GET "http://127.0.0.1:8000/jobs/JOB-HIST-DEMO-01/who-could?action=prepare&at=2026-10-03T14:00:00Z" \
  -H "X-User-Id: om-agrawal" | python -m json.tool
```

### 7. Grant Roles Across Multi-Scope Lists in One Transaction
```bash
curl -s -X POST "http://127.0.0.1:8000/grants" \
  -H "X-User-Id: om-agrawal" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "zoya-ansari",
    "grants": [
      {"role_id": "maker", "branch_id": "BR-MUM", "effect": "allow", "reason": "Assigned Mumbai import desk"},
      {"role_id": "checker", "client_id": "C01", "branch_id": "BR-MUM", "effect": "allow", "reason": "Checker for C01"}
    ]
  }'
```

---

## 7. Assumptions & What Was Cut

### Assumptions:
1. **Authentication Gateway**: Authentication is delegated to an external identity provider / reverse proxy that injects `X-User-Id` (and optional `X-Run-Id`).
2. **Injectable Clock**: `app/clock.py` provides an injectable `get_now()` enabling time-travel and past replay tests without altering system clock.
3. **UTC Everywhere**: All database columns and API models enforce timezone-aware UTC timestamps.

### What Was Cut & Why:
- **Decision Caching**: Intentionally omitted. In customs brokerage, instant revocation is critical. Direct SQL execution guarantees zero-lag revocation and avoids caching stale authorization grants across distributed workers.
- **Frontend / Custom UI**: Swagger UI (`/docs`) provides a standardized, interactive web UI for testing all operations without client-side overhead.
- **Complex Hierarchy Engines**: We avoided graph database dependencies. Flat dimensional grants with wildcard (`NULL`) support and explicit `deny` precedence satisfy all customs requirements with relational speed and simplicity.

---

## 8. Sources and AI Assistance

- **AI Assistance**: An AI coding assistant was used for scaffolding, writing boilerplate tests, and drafting documentation. Every design decision and line of policy logic was reviewed, verified, and tested by the author.
- **External Libraries & Documentation Consulted**:
  - FastAPI (documentation & OpenAPI routing)
  - SQLAlchemy 2.0 (core query compilation, hybrid properties, bulk mappings)
  - SQLite documentation (WAL mode, index optimizations, relational trigger syntax)
  - pytest & httpx (test isolation fixtures, ASGI test client lifecycle)
  - uvicorn (ASGI web server)
  - pydantic v2 (schema validation, field aliases, model serialization)

**Submitted by**: Atharva (Atrv3000), November 5, 2026; tools used: Python 3.11+, FastAPI, SQLAlchemy 2.0, SQLite WAL, pytest, httpx, uvicorn, Git, Antigravity AI assistant
