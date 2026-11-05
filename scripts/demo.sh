#!/usr/bin/env bash
# ==============================================================================
# Nagarkot Access Control Service - 5-Minute Executable Demo Script
# ==============================================================================
set -e

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "========================================================================"
echo " 1. SYSTEM HEALTH CHECK"
echo "========================================================================"
curl -s "${BASE_URL}/health" | python -c "
import sys, json
d = json.load(sys.stdin)
print(json.dumps(d, indent=2))
assert d.get('status') == 'ok', 'Health check failed'
print('--> [PASS] Step 1: Health check OK')
"

echo -e "\n========================================================================"
echo " 2. MAKER-CHECKER SEPARATION OF DUTIES (SoD)"
echo " Scenario: Asha Rao prepared job JOB-SHOWCASE-02 for client C03."
echo " She holds Checker for C03, but the 4-eyes rule forbids self-checking."
echo "========================================================================"
echo "A) Evaluating Asha checking her own prepared job (JOB-SHOWCASE-02):"
curl -s -X GET "${BASE_URL}/decide?user_id=asha-rao&action=check&job_id=JOB-SHOWCASE-02" \
  -H "X-User-Id: asha-rao" | python -c "
import sys, json
d = json.load(sys.stdin)
print(f'Allowed: {d[\"allowed\"]}, Outcome: {d[\"outcome\"]}, Primary Reason: {d[\"primary_reason\"]}')
assert not d['allowed'] and d['primary_reason'] == 'SOD_VIOLATION_MAKER_CHECKER', 'Expected SoD block'
print('--> [PASS] Step 2A: Self-checking blocked by SoD')
"

echo "B) Evaluating Asha checking job JOB-SHOWCASE-03 (Client C05, prepared by Imran Shaikh):"
curl -s -X GET "${BASE_URL}/decide?user_id=asha-rao&action=check&job_id=JOB-SHOWCASE-03" \
  -H "X-User-Id: asha-rao" | python -c "
import sys, json
d = json.load(sys.stdin)
print(f'Allowed: {d[\"allowed\"]}, Outcome: {d[\"outcome\"]}, Matched Grants: {d[\"matched_grants\"]}')
assert d['allowed'] and d['outcome'] == 'ALLOW', 'Expected ALLOW on others prepared job'
print('--> [PASS] Step 2B: Asha allowed to check job prepared by someone else')
"

echo -e "\n========================================================================"
echo " 3. NARROW-SCOPE CHECKER (ROHIT MEHTA)"
echo " Rohit is Checker for: Client C01 / Branch Mumbai-Fort / Direction IMPORT."
echo "========================================================================"
echo "A) Evaluating JOB-SHOWCASE-05 (C01 / Mumbai-Fort / IMPORT / AIR) -> Expected: ALLOW"
curl -s -X GET "${BASE_URL}/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-05" \
  -H "X-User-Id: rohit-mehta" | python -c "
import sys, json
d = json.load(sys.stdin)
print(f'Allowed: {d[\"allowed\"]}, Outcome: {d[\"outcome\"]}, Matched Grants: {d[\"matched_grants\"]}')
assert d['allowed'] and d['outcome'] == 'ALLOW', 'Expected ALLOW'
print('--> [PASS] Step 3A: Rohit allowed within exact 4-dimensional scope')
"

echo "B) Evaluating JOB-SHOWCASE-06 (C01 / Mumbai-Fort / EXPORT / AIR) -> Expected: DENY (Direction)"
curl -s -X GET "${BASE_URL}/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-06" \
  -H "X-User-Id: rohit-mehta" | python -c "
import sys, json
d = json.load(sys.stdin)
print(f'Allowed: {d[\"allowed\"]}, Primary Reason: {d[\"primary_reason\"]}')
assert not d['allowed'] and d['primary_reason'] == 'NO_GRANT', 'Expected DENY due to direction mismatch'
print('--> [PASS] Step 3B: Rohit denied on EXPORT shipment')
"

echo "C) Evaluating JOB-SHOWCASE-07 (C01 / Nhava Sheva / IMPORT / AIR) -> Expected: DENY (Branch)"
curl -s -X GET "${BASE_URL}/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-07" \
  -H "X-User-Id: rohit-mehta" | python -c "
import sys, json
d = json.load(sys.stdin)
print(f'Allowed: {d[\"allowed\"]}, Primary Reason: {d[\"primary_reason\"]}')
assert not d['allowed'] and d['primary_reason'] == 'NO_GRANT', 'Expected DENY due to branch mismatch'
print('--> [PASS] Step 3C: Rohit denied on other branch')
"

echo -e "\n========================================================================"
echo " 4. EXPLAIN & COMPARE ('Why can Priya do this and Faisal cannot?')"
echo " Action 'check' on PREPARED job JOB-SHOWCASE-05"
echo "========================================================================"
curl -s -X GET "${BASE_URL}/explain/compare?users=priya-nair,faisal-khan&action=check&job_id=JOB-SHOWCASE-05" \
  -H "X-User-Id: om-agrawal" | python -c "
import sys, json
d = json.load(sys.stdin)
print('Comparison Summary:\n' + d['comparison_summary'])
assert 'priya-nair' in d['comparison_summary'] and 'faisal-khan' in d['comparison_summary']
print('--> [PASS] Step 4: Side-by-side comparison explain verified')
"

echo -e "\n========================================================================"
echo " 5. ABSENTEE COVER (IMRAN SHAIKH & POOJA SHARMA)"
echo " Imran is ABSENT at Delhi-ICD. Pooja has a 7-day cover grant as Maker."
echo " Shipment JOB-SHOWCASE-08 is CONFIRMED at Delhi-ICD awaiting 'prepare'."
echo "========================================================================"
echo "A) Imran attempting 'prepare' while marked ABSENT:"
curl -s -X GET "${BASE_URL}/decide?user_id=imran-shaikh&action=prepare&job_id=JOB-SHOWCASE-08" \
  -H "X-User-Id: imran-shaikh" | python -c "
import sys, json
d = json.load(sys.stdin)
print(f'Allowed: {d[\"allowed\"]}, Primary Reason: {d[\"primary_reason\"]}')
assert not d['allowed'] and d['primary_reason'] == 'USER_ABSENT', 'Expected USER_ABSENT'
print('--> [PASS] Step 5A: Absent user blocked from acting')
"

echo "B) Pooja acting under active cover grant:"
curl -s -X GET "${BASE_URL}/decide?user_id=pooja-sharma&action=prepare&job_id=JOB-SHOWCASE-08" \
  -H "X-User-Id: pooja-sharma" | python -c "
import sys, json
d = json.load(sys.stdin)
print(f'Allowed: {d[\"allowed\"]}, Matched Grants: {d[\"matched_grants\"]}')
assert d['allowed'] and 'grt-pooja-cover-imran' in d['matched_grants'], 'Expected cover grant match'
print('--> [PASS] Step 5B: Temporary absence cover grant authorized')
"

echo -e "\n========================================================================"
echo " 6. STUCK-JOB RESOLUTION (OPS ADMIN OVERRIDE SEND-BACK)"
echo " Meera Iyer (Ops Admin) sends stalled PREPARED job back to CONFIRMED."
echo "========================================================================"
curl -s -X POST "${BASE_URL}/jobs/JOB-SHOWCASE-03/actions/override_send_back" \
  -H "X-User-Id: meera-iyer" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Shipment stalled due to preparer absence; sending back to CONFIRMED for reprocessing"}' | python -c "
import sys, json
d = json.load(sys.stdin)
print(json.dumps(d, indent=2))
assert d.get('current_stage') == 'CONFIRMED', 'Expected current_stage CONFIRMED'
print('--> [PASS] Step 6: Ops Admin override executed and audited')
"

echo -e "\n========================================================================"
echo " 7. TWO-PERSON APPROVAL WORKFLOW ON FILED SHIPMENTS"
echo " Sunita requests cancellation on FILED job JOB-SHOWCASE-01"
echo "========================================================================"
APP_ID=$(curl -s -X POST "${BASE_URL}/jobs/JOB-SHOWCASE-01/actions/cancel_filed" \
  -H "X-User-Id: sunita-patil" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Client cancelled shipment after filing due to port strike"}' | python -c "
import sys, json
d = json.load(sys.stdin)
print(json.dumps(d, indent=2), file=sys.stderr)
assert d.get('status') == 'NEEDS_APPROVAL', 'Expected NEEDS_APPROVAL'
print(d.get('approval_id', ''))
")
echo "Created pending Approval ID: ${APP_ID}"
echo "--> [PASS] Step 7A: Sensitive action held in pending approval"

echo "Attempting self-approval by Sunita (requester == decider) -> Expected: 403 Forbidden"
curl -s -w "\nHTTP_STATUS:%{http_code}\n" -X POST "${BASE_URL}/approvals/${APP_ID}/approve" \
  -H "X-User-Id: sunita-patil" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Attempting self approval"}' | python -c "
import sys
content = sys.stdin.read()
print(content.strip())
assert 'HTTP_STATUS:403' in content, 'Expected 403 Forbidden for self-approval'
print('--> [PASS] Step 7B: Self-approval rejected by separation of duty')
"

echo -e "\n========================================================================"
echo " 8. ADMIN SELF-ESCALATION DEFENCE"
echo " Deepak Verma (Access Admin) tries to self-grant or grant privileged roles."
echo "========================================================================"
echo "A) Deepak attempting self-grant -> Expected: 403 Forbidden"
curl -s -w "\nHTTP_STATUS:%{http_code}\n" -X POST "${BASE_URL}/grants" \
  -H "X-User-Id: deepak-verma" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "deepak-verma", "grants": [{"role_id": "maker", "branch_id": "BR-MUM", "effect": "allow", "reason": "Self-grant attempt"}]}' | python -c "
import sys
content = sys.stdin.read()
print(content.strip())
assert 'HTTP_STATUS:403' in content, 'Expected 403 Forbidden for self-grant'
print('--> [PASS] Step 8A: Self-grant prohibited')
"

echo "B) Deepak attempting to grant privileged role 'super_admin' -> Expected: 403 Forbidden"
curl -s -w "\nHTTP_STATUS:%{http_code}\n" -X POST "${BASE_URL}/grants" \
  -H "X-User-Id: deepak-verma" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "faisal-khan", "grants": [{"role_id": "super_admin", "branch_id": "BR-MUM", "effect": "allow", "reason": "Privilege escalation"}]}' | python -c "
import sys
content = sys.stdin.read()
print(content.strip())
assert 'HTTP_STATUS:403' in content, 'Expected 403 Forbidden for privileged grant'
print('--> [PASS] Step 8B: Privileged role grant blocked')
"

echo -e "\n========================================================================"
echo " 9. HISTORICAL TIME-TRAVEL ('Who could have changed this on Oct 3rd?')"
echo "========================================================================"
curl -s -X GET "${BASE_URL}/jobs/JOB-HIST-DEMO-01/who-could?action=check&at=2026-10-03T15:00:00Z" \
  -H "X-User-Id: om-agrawal" | python -c "
import sys, json
d = json.load(sys.stdin)
actual = d.get('actual_actor', {})
actual_id = actual.get('actor_id') if isinstance(actual, dict) else actual
print(f'Actual Actor: {actual_id}')
actors = [a['name'] for a in d.get('actors_who_could', [])]
print(f'Eligible Actors at that date: {actors}')
assert actual_id == 'rohit-mehta', f'Expected actual actor rohit-mehta, got {actual_id}'
assert len(actors) > 0, 'Expected at least one eligible actor'
print('--> [PASS] Step 9: Historical point-in-time actors reconstructed')
"

echo -e "\n========================================================================"
echo " 10. CHRONOLOGICAL JOB HISTORY"
echo "========================================================================"
curl -s -X GET "${BASE_URL}/jobs/JOB-SHOWCASE-01/history" \
  -H "X-User-Id: meera-iyer" | python -c "
import sys, json
events = json.load(sys.stdin)
print(f'Recorded {len(events)} chronological lifecycle events for JOB-SHOWCASE-01:')
for ev in events:
    print(f'  [{ev[\"at\"]}] {ev[\"actor_id\"]} ({ev[\"actor_type\"]}) -> {ev[\"action\"]} ({ev[\"decision\"]})')
assert len(events) >= 4, 'Expected at least 4 lifecycle events'
print('--> [PASS] Step 10: Full immutable audit trail displayed')
"

echo -e "\n========================================================================"
echo " 11. CLIENT DATA REDACTION & ISOLATION"
echo " Rajesh Gupta (Client C01 user) viewing shipment JOB-SHOWCASE-01"
echo "========================================================================"
curl -s -X GET "${BASE_URL}/jobs/JOB-SHOWCASE-01" \
  -H "X-User-Id: rajesh-gupta" | python -c "
import sys, json
d = json.load(sys.stdin)
print(f'Client ID: {d[\"client_id\"]}')
print(f'internal_notes: {d[\"internal_notes\"]}')
print(f'assigned_to:    {d[\"assigned_to\"]}')
print(f'prepared_by:    {d[\"prepared_by\"]}')
assert d['internal_notes'] is None and d['assigned_to'] is None and d['prepared_by'] is None, 'Expected redaction'
print('--> [PASS] Step 11: Internal fields successfully redacted for client user')
"

echo -e "\n========================================================================"
echo " ALL DEMO STEPS EXECUTED AND VERIFIED: PASS"
echo "========================================================================"
