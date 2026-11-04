# 5-Minute Evaluation Demo Script

This document provides a timed walkthrough demonstrating how the Nagarkot Access Control Service resolves real-world customs brokerage operational challenges, guarantees zero-trust security, and enforces separation of duties.

---

## Prerequisites
1. Ensure the API server is running:
   ```bash
   make run
   # or: ./.venv/bin/uvicorn app.main:app --port 8000
   ```
2. Ensure the deterministic seed database is loaded:
   ```bash
   make seed
   ```

---

## ⏱️ Minute 0:00 - 1:00: Overview & Health Check
### Narrative
"Nagarkot Forwarders Pvt. Ltd. operates 5 branches handling thousands of shipments across air and sea freight. Following an incident where a filed customs shipment was improperly altered, this service acts as the central policy decision engine answering: **who may do what on which job?**"

### Action: Health Check
```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```
**Expected Output**:
```json
{
    "status": "ok",
    "service": "nagarkot-access-control"
}
```

---

## ⏱️ Minute 1:00 - 2:00: The 4-Eyes Principle (SoD)
### Narrative
"Customs regulations require strict separation of duties: the maker who prepares a customs checklist cannot check their own declaration.
Consider **Asha Rao**: she is the National Maker everywhere, and also an assigned Checker for client `C03`. Job `NF-SHOWCASE-PREPARED-SOD` was prepared by Asha for client `C03`. Even though she holds the Checker role for `C03`, can she check it?"

### Action: Evaluate Maker-Checker Conflict
```bash
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=asha-rao&action=check&job_id=JOB-SHOWCASE-02" \
  -H "X-User-Id: asha-rao" | python -m json.tool
```

### Key Observation:
- `allowed: false`
- `primary_reason: "SOD_VIOLATION_MAKER_CHECKER"`
- Trace confirms checks 1–6 passed (Role covers scope, user is active, etc.), but Check 7 (`SOD_OK`) blocked the action.

---

## ⏱️ Minute 2:00 - 3:00: Multidimensional Scope & Denial Precedence
### Narrative
"Access at Nagarkot is granted across 4 dimensions: Client, Branch, Direction (Import/Export), and Mode (Air/FCL/LCL).
**Rohit Mehta** is restricted to checking `C01 / Mumbai-Fort / IMPORT`.
Let us compare him against two jobs:"

### Action: Rohit on Allowed Scope vs Disallowed Scope
```bash
# Allowed: C01 / Mumbai-Fort / IMPORT
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-01" \
  -H "X-User-Id: rohit-mehta"

# Denied: C03 (Different Client)
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-02" \
  -H "X-User-Id: rohit-mehta"
```

### Explain & Compare Endpoint
"When an auditor asks: *Why can Priya check this job and Faisal cannot?*"
```bash
curl -s -X GET "http://127.0.0.1:8000/explain/compare?users=priya-nair,faisal-khan&action=check&job_id=JOB-SHOWCASE-01" \
  -H "X-User-Id: om-agrawal" | python -m json.tool
```
**Output**:
> *"User 'priya-nair' is ALLOWED (ALLOW) via grants ['grt-priya-chk-all'], whereas User 'faisal-khan' is DENIED due to NO_GRANT."*

---

## ⏱️ Minute 3:00 - 4:00: Absentee Handover & Historical Time-Travel
### Narrative
"What happens when staff are absent? **Imran Shaikh** at Delhi-ICD is absent on medical leave. His active operational rights are immediately suspended, while **Pooja Sharma** holds a time-bounded 7-day cover grant."

### Action: Imran vs Pooja at Delhi-ICD
```bash
# Imran: Fails with USER_ABSENT
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=imran-shaikh&action=prepare&job_id=JOB-SHOWCASE-03" \
  -H "X-User-Id: imran-shaikh"

# Pooja: Succeeds via cover grant
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=pooja-sharma&action=prepare&job_id=JOB-SHOWCASE-03" \
  -H "X-User-Id: pooja-sharma"
```

### Historical "Who Could Have Changed This on Oct 3rd?"
"Using temporal versioning and audit event reconstruction, the system can time-travel to reproduce permissions at any prior second:"
```bash
curl -s -X GET "http://127.0.0.1:8000/jobs/JOB-HIST-DEMO-01/who-could?action=prepare&at=2026-10-03T14:00:00Z" \
  -H "X-User-Id: om-agrawal" | python -m json.tool
```

---

## ⏱️ Minute 4:00 - 5:00: Two-Person Rule on FILED Jobs & Client Privacy
### Narrative
"The incident that sparked this project occurred when a filed shipment was modified. In our system, once a job reaches `FILED`, nobody can alter or cancel it directly. Any attempt returns `NEEDS_APPROVAL` and mandates a 2-person approval workflow."

### Action: Cancelling a FILED Job
```bash
curl -s -X POST "http://127.0.0.1:8000/jobs/JOB-SHOWCASE-01/actions/cancel_filed" \
  -H "X-User-Id: sunita-patil" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Customs inspection failed at terminal; cancellation requested"}' | python -m json.tool
```
**Result**:
- Returns `status: "NEEDS_APPROVAL"`, generates approval ID `APP-...`.
- Self-approval is rejected by database triggers and decision logic.
- A second approver must review and approve.

### Client User Privacy (Rajesh Gupta - Client C01)
"Client users only see their own client's shipments, and internal staff notes, operational assignees, and preparation handlers are strictly redacted:"
```bash
curl -s -X GET "http://127.0.0.1:8000/jobs/JOB-SHOWCASE-01" \
  -H "X-User-Id: rajesh-gupta" | python -m json.tool
```
Internal fields (`internal_notes`, `assigned_to`, `prepared_by`, `checked_by`, `filed_by`) return as `null`.

---

## Quick One-Command Execution
You can run the entire automated demo at any time using:
```bash
bash scripts/demo.sh
```
