# Nagarkot Forwarders - Access Control Service (ACS)

> **Production-grade Access Control & Policy Decision Service for Nagarkot Forwarders Pvt. Ltd.**  
> Built with FastAPI, SQLAlchemy 2.0, SQLite WAL, and deterministic zero-trust authorization.

---

## 1. What It Is
Nagarkot Forwarders Pvt. Ltd. is a licensed customs brokerage (~120 staff, 5 branches) handling thousands of import and export shipments across air and sea freight. Following an incident where a filed customs entry was improperly altered, this service acts as the central policy decision engine answering: **who may do what on which job (shipment)?**

Key Capabilities:
- **8-Stage Deterministic Decision Pipeline**: Strict check evaluation with clear precedence and full explanation traces.
- **Multidimensional Scopes & Explicit Deny Override**: Access mapped across Client, Branch, Direction (Import/Export), and Mode (Air/FCL/LCL). Deny grants unconditionally override allow grants.
- **Four-Eyes Principle (Separation of Duties)**: Maker cannot Check their own preparation in the current cycle; Requester cannot approve their own sensitive action.
- **Two-Person Rule on FILED Shipments**: Once filed with Customs, a shipment cannot be modified or cancelled directly. Sensitive actions mandate approval by an authorized `Approver`.
- **High-Performance SQL Compilation**: Python decision logic compiles directly into optimized SQL predicates for `/me/queue` and `/jobs` pagination, achieving **p95 < 27ms across 200,000 jobs**.
- **Immutable Append-Only Audit Logging**: SQLite relational triggers block `UPDATE` and `DELETE` at the database engine level.

---

## 2. 5-Step Quickstart

### Step 1: Clone and Set Up Virtual Environment
```bash
git clone <repository_url> nagarkot
cd nagarkot
make setup
```
*(Creates `.venv` and installs pinned dependencies from `requirements.txt`)*

### Step 2: Seed the Deterministic Dataset
```bash
make seed
```
*(Populates 5 branches, 10 clients, 20 personas + Zoya, showcase jobs, and 300 shipments with 30-day history using seed=42)*

### Step 3: Run the Test Suite
```bash
make test
```
*(Runs pytest across all 40 tests, including queue SQL-Python equivalence and fail-closed guards)*

### Step 4: Run the Benchmark (200k Jobs)
```bash
make scale
make bench
```
*(Generates 200,000 shipments across 500 users and measures p50/p90/p95/p99 query latencies)*

### Step 5: Start the API Server
```bash
make run
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
| `NF-SHOWCASE-PREPARED-SOD` | `JOB-SHOWCASE-02` | C03 / Mumbai-Fort / IMPORT / AIR | `PREPARED` | **Separation of Duties (SoD)**: Prepared by Asha Rao. Asha holds Checker for C03, but is denied check due to `SOD_VIOLATION_MAKER_CHECKER`. |
| `NF-SHOWCASE-STUCK` | `JOB-SHOWCASE-03` | C05 / Delhi-ICD / IMPORT / FCL | `PREPARED` | **Ops Admin Override**: Prepared by absent user Imran Shaikh. Meera Iyer can roll back to `CONFIRMED` via `override_send_back` with reason. |
| `NF-SHOWCASE-ARJUN-REVOKED` | `JOB-SHOWCASE-04` | C08 / Mumbai-Fort / IMPORT / AIR | `PREPARED` | **Auto-Unassignment**: Was assigned to Arjun Reddy; auto-unassigned and returned to pool when his grant was revoked yesterday. |
| `NF-IMP-AIR-OCT03` | `JOB-HIST-DEMO-01` | C01 / Mumbai-Fort / IMPORT / AIR | `FILED` | **Historical Time-Travel**: Historical shipment with backdated events from 30+ days ago to answer *"Who could have changed this on Oct 3rd?"*. |

---

## 5. Performance Benchmark Results (200,000 Jobs, 500 Users)

Measured on SQLite in WAL mode with composite B-tree indexes and keyset pagination:

| Scenario | Min (ms) | Mean (ms) | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Target SLA | Result |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **GET /me/queue** (Asha Rao - National Maker) | 9.88 | 14.79 | 14.21 | 19.91 | **24.08** | 31.69 | < 200 ms | **PASS** |
| **GET /me/queue** (Rohit Mehta - Restricted Checker) | 8.82 | 14.60 | 13.26 | 21.76 | **26.86** | 32.23 | < 200 ms | **PASS** |
| **GET /me/queue** (Pooja Sharma - Checker + Delhi Cover) | 9.50 | 11.15 | 10.98 | 12.52 | **12.68** | 13.86 | < 200 ms | **PASS** |
| **GET /me/queue** (Neha Kulkarni - Filer MUM & NS) | 8.37 | 12.35 | 11.40 | 16.40 | **19.47** | 24.56 | < 200 ms | **PASS** |
| **GET /jobs** (Asha Rao - Staff View First Page) | 7.98 | 10.27 | 9.56 | 13.72 | **14.62** | 15.79 | < 200 ms | **PASS** |
| **GET /jobs** (Rajesh Gupta - Client User C01 View) | 7.49 | 10.92 | 9.50 | 16.27 | **17.75** | 22.67 | < 200 ms | **PASS** |

> **Key Takeaway**: p95 latency is between **12ms and 27ms**, nearly **10x faster** than the 200ms SLA target, with zero caching.

---

## 6. API Cheat Sheet & Curl Examples

All endpoints authenticate callers via the `X-User-Id` HTTP header.

### 1. Dry Run a Decision (Pure Read, No Audit Log)
```bash
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=asha-rao&action=check&job_id=JOB-SHOWCASE-02" \
  -H "X-User-Id: asha-rao" | python -m json.tool
```

### 2. Side-by-Side Explanation ("Why can she and he can't?")
```bash
curl -s -X GET "http://127.0.0.1:8000/explain/compare?users=priya-nair,faisal-khan&action=check&job_id=JOB-SHOWCASE-01" \
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
- **Decision Caching**: Intentionally omitted. In customs brokerage, instant revocation is critical. Because covering indexes provide sub-25ms response times at 200,000 jobs, caching would introduce stale authorization windows with no performance benefit.
- **Frontend / Custom UI**: Swagger UI (`/docs`) provides a standardized, interactive web UI for testing all operations without client-side overhead.
- **Complex Hierarchy Engines**: We avoided graph database dependencies. Flat dimensional grants with wildcard (`NULL`) support and explicit `deny` precedence satisfy all customs requirements with relational speed and simplicity.

---

## 8. Sources & AI Assistance

- **Frameworks & Libraries**:
  - FastAPI 0.115 & Pydantic v2 for typed validation and OpenAPI schema generation.
  - SQLAlchemy 2.0 for relational query compilation and bulk operations.
  - SQLite with Write-Ahead Logging (WAL) and native relational triggers.
- **AI Assistance**:
  - Developed with pair-programming assistance from Antigravity (Google DeepMind Advanced Agentic Coding). AI assisted with architecting the 8-stage decision pipeline, drafting test fixtures, and verifying keyset pagination equivalence.
