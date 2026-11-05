# 5-Minute Evaluation Demo Script

This document provides a timed walkthrough demonstrating how the Nagarkot Access Control Service resolves real-world customs brokerage operational challenges, guarantees zero-trust security, and enforces separation of duties.

---

## Prerequisites
1. Ensure the API server is running:
   ```bash
   uvicorn app.main:app --port 8000
   ```
2. Ensure the deterministic seed database is loaded:
   ```bash
   python scripts/seed.py
   ```

---

## ⏱️ Minute 0:00 - 1:00: Overview & Health Check
### Narrative
"Nagarkot Forwarders Pvt. Ltd. operates 5 branches handling thousands of shipments across air and sea freight. Following an incident where a filed customs shipment was improperly altered, this service acts as the central policy decision engine answering: **who may do what on which job?**"

### Action: Health Check
```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```
**Output**:
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
Consider **Asha Rao**: she is the National Maker everywhere, and also an assigned Checker for client `C03`. Job `JOB-SHOWCASE-02` was prepared by Asha for client `C03`. Even though she holds the Checker role for `C03`, can she check it?"

### Action 2A: Evaluate Maker-Checker Conflict on Self-Prepared Job
```bash
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=asha-rao&action=check&job_id=JOB-SHOWCASE-02" \
  -H "X-User-Id: asha-rao" | python -m json.tool
```
**Output**:
```json
{
    "allowed": false,
    "outcome": "DENY",
    "primary_reason": "SOD_VIOLATION_MAKER_CHECKER"
}
```
*Check 7 (`SOD_OK`) blocks self-approval.*

### Action 2B: Asha Checking Another Preparer's Job (Client C05)
```bash
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=asha-rao&action=check&job_id=JOB-SHOWCASE-03" \
  -H "X-User-Id: asha-rao" | python -m json.tool
```
**Output**:
```json
{
    "allowed": true,
    "outcome": "ALLOW",
    "matched_grants": ["grt-asha-chk-C05"]
}
```
*Asha CAN check others' prepared jobs within her C05 checker scope.*

---

## ⏱️ Minute 2:00 - 3:00: Multidimensional Scope & Denial Precedence
### Narrative
"Access at Nagarkot is granted across 4 dimensions: Client, Branch, Direction (Import/Export), and Mode (Air/FCL/LCL).
**Rohit Mehta** is restricted to: `Client C01 / Branch Mumbai-Fort / Direction IMPORT`."

### Action 3A: Allowed Within Exact Scope
```bash
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-05" \
  -H "X-User-Id: rohit-mehta" | python -m json.tool
```
**Output**: `allowed: true`, `outcome: "ALLOW"`, `matched_grants: ["grt-rohit-chk"]`.

### Action 3B: Denied on EXPORT Direction Mismatch
```bash
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-06" \
  -H "X-User-Id: rohit-mehta" | python -m json.tool
```
**Output**: `allowed: false`, `primary_reason: "NO_GRANT"`. Check 6 detail: Direction EXPORT mismatch.

### Action 3C: Denied on Branch Mismatch (Nhava Sheva)
```bash
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-07" \
  -H "X-User-Id: rohit-mehta" | python -m json.tool
```
**Output**: `allowed: false`, `primary_reason: "NO_GRANT"`. Check 6 detail: Branch Nhava Sheva mismatch.

### Action 4: Explain & Compare ("Why can Priya check this and Faisal cannot?")
```bash
curl -s -X GET "http://127.0.0.1:8000/explain/compare?users=priya-nair,faisal-khan&action=check&job_id=JOB-SHOWCASE-05" \
  -H "X-User-Id: om-agrawal" | python -m json.tool
```
**Output**:
> *"User 'priya-nair' is ALLOWED (ALLOW) via grants ['grt-priya-chk-all'], whereas User 'faisal-khan' is DENIED due to NO_GRANT."*

---

## ⏱️ Minute 3:00 - 4:00: Absentee Handover & Historical Time-Travel
### Narrative
"What happens when staff are absent? **Imran Shaikh** at Delhi-ICD is absent on medical leave. His active operational rights are immediately suspended, while **Pooja Sharma** holds a time-bounded 7-day cover grant as Maker at Delhi-ICD."

### Action 5: Imran (Absent) vs Pooja (Cover Grant) on CONFIRMED Shipment JOB-SHOWCASE-08
```bash
# Imran: Fails at Check 2 with USER_ABSENT
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=imran-shaikh&action=prepare&job_id=JOB-SHOWCASE-08" \
  -H "X-User-Id: imran-shaikh"

# Pooja: Succeeds via temporary cover grant
curl -s -X GET "http://127.0.0.1:8000/decide?user_id=pooja-sharma&action=prepare&job_id=JOB-SHOWCASE-08" \
  -H "X-User-Id: pooja-sharma"
```
**Outputs**:
- Imran: `allowed: false`, `primary_reason: "USER_ABSENT"`.
- Pooja: `allowed: true`, `matched_grants: ["grt-pooja-cover-imran"]`.

### Action 6: Ops Admin Override on Stuck Job
```bash
curl -s -X POST "http://127.0.0.1:8000/jobs/JOB-SHOWCASE-03/actions/override_send_back" \
  -H "X-User-Id: meera-iyer" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Shipment stalled due to preparer absence; sending back to CONFIRMED for reprocessing"}'
```
**Output**:
```json
{
    "status": "EXECUTED",
    "job_id": "JOB-SHOWCASE-03",
    "action": "override_send_back",
    "current_stage": "CONFIRMED"
}
```

---

## ⏱️ Minute 4:00 - 5:00: Two-Person Rule, Admin Safeguards & Privacy
### Narrative
"In our system, once a job reaches `FILED`, nobody can alter or cancel it directly. Any attempt returns `NEEDS_APPROVAL` and mandates a 2-person approval workflow."

### Action 7: Cancelling a FILED Job & Guarding Against Self-Approval
```bash
# 7A. Sunita Patil requests cancel_filed on JOB-SHOWCASE-01
curl -s -X POST "http://127.0.0.1:8000/jobs/JOB-SHOWCASE-01/actions/cancel_filed" \
  -H "X-User-Id: sunita-patil" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Client cancelled shipment after filing due to port strike"}'
```
**Output**:
```json
{
    "status": "NEEDS_APPROVAL",
    "approval_id": "APP-...",
    "message": "Sensitive action submitted for 2-person authorization to Approver"
}
```

```bash
# 7B. Sunita attempts to approve her own request
curl -s -i -X POST "http://127.0.0.1:8000/approvals/<APPROVAL_ID>/approve" \
  -H "X-User-Id: sunita-patil" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Attempting self approval"}'
```
**Output**: `HTTP/1.1 403 Forbidden` (`Separation of duties violation: approver cannot be the same user who requested the sensitive action`).

### Action 8: Admin Self-Escalation Defence
```bash
# Deepak Verma attempts self-grant
curl -s -i -X POST "http://127.0.0.1:8000/grants" \
  -H "X-User-Id: deepak-verma" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "deepak-verma", "grants": [{"role_id": "maker", "branch_id": "BR-MUM", "effect": "allow", "reason": "Self-grant attempt"}]}'
# Result: 403 Forbidden (Self-escalation violation: users cannot grant roles to themselves)

# Deepak attempts to grant privileged role super_admin
curl -s -i -X POST "http://127.0.0.1:8000/grants" \
  -H "X-User-Id: deepak-verma" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "faisal-khan", "grants": [{"role_id": "super_admin", "branch_id": "BR-MUM", "effect": "allow", "reason": "Privilege escalation"}]}'
# Result: 403 Forbidden (Role 'super_admin' is privileged; granting requires access.manage_privileged)
```

### Action 9: Historical Time-Travel ("Who could have checked this on Oct 3rd?")
```bash
curl -s -X GET "http://127.0.0.1:8000/jobs/JOB-HIST-DEMO-01/who-could?action=check&at=2026-10-03T15:00:00Z" \
  -H "X-User-Id: om-agrawal" | python -m json.tool
```
**Output**:
- `actual_actor`: `rohit-mehta`
- `actors_who_could`: `['Rohit Mehta', 'Pooja Sharma', 'Priya Nair']`

### Action 10: Complete Chronological Job History
```bash
curl -s -X GET "http://127.0.0.1:8000/jobs/JOB-SHOWCASE-01/history" \
  -H "X-User-Id: meera-iyer" | python -m json.tool
```
**Output**: Chronological immutable events showing parser creation, prepare, check, and filing.

### Action 11: Client User Privacy (Rajesh Gupta - Client C01)
```bash
curl -s -X GET "http://127.0.0.1:8000/jobs/JOB-SHOWCASE-01" \
  -H "X-User-Id: rajesh-gupta" | python -m json.tool
```
**Output**:
Internal fields (`internal_notes`, `assigned_to`, `prepared_by`, `checked_by`, `filed_by`) return as `null`.

---

## Quick One-Command Execution
You can run the entire automated demo at any time using:
```bash
bash scripts/demo.sh
```
Every step automatically validates responses and reports `--> [PASS]`.
