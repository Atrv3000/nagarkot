#!/usr/bin/env bash
# ==============================================================================
# Nagarkot Access Control Service - 5-Minute Executable Demo Script
# ==============================================================================
set -e

BASE_URL="http://127.0.0.1:8000"

echo "========================================================================"
echo " 1. SYSTEM HEALTH CHECK"
echo "========================================================================"
curl -s "${BASE_URL}/health" | python -m json.tool

echo -e "\n========================================================================"
echo " 2. MAKER-CHECKER SEPARATION OF DUTIES (SoD)"
echo " Scenario: Asha Rao prepared job NF-SHOWCASE-PREPARED-SOD for client C03."
echo " She holds Checker for C03, but the 4-eyes rule forbids self-checking."
echo "========================================================================"
curl -s -X GET "${BASE_URL}/decide?user_id=asha-rao&action=check&job_id=JOB-SHOWCASE-02" \
  -H "X-User-Id: asha-rao" | python -m json.tool

echo -e "\n========================================================================"
echo " 3. NARROW SCOPE CHECKER (ROHIT MEHTA)"
echo " Rohit is Checker for C01 / Mumbai-Fort / IMPORT only."
echo " A) Evaluating C01 / Mumbai-Fort / IMPORT (Should be ALLOWED):"
curl -s -X GET "${BASE_URL}/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-01" \
  -H "X-User-Id: rohit-mehta" | python -c "import sys, json; data=json.load(sys.stdin); print(f'Allowed: {data[\"allowed\"]}, Outcome: {data[\"outcome\"]}, Matched Grants: {data[\"matched_grants\"]}')"

echo " B) Evaluating C03 / Mumbai-Fort / IMPORT (Should be DENIED):"
curl -s -X GET "${BASE_URL}/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-02" \
  -H "X-User-Id: rohit-mehta" | python -c "import sys, json; data=json.load(sys.stdin); print(f'Allowed: {data[\"allowed\"]}, Reason: {data[\"primary_reason\"]}')"

echo -e "\n========================================================================"
echo " 4. ABSENTEE COVER (IMRAN SHAIKH & POOJA SHARMA)"
echo " Imran is ABSENT at Delhi-ICD. Pooja has a temporary 7-day cover grant."
echo "========================================================================"
echo " A) Imran Shaikh attempting action 'prepare' at Delhi:"
curl -s -X GET "${BASE_URL}/decide?user_id=imran-shaikh&action=prepare&job_id=JOB-SHOWCASE-03" \
  -H "X-User-Id: imran-shaikh" | python -c "import sys, json; data=json.load(sys.stdin); print(f'Imran Allowed: {data[\"allowed\"]}, Primary Reason: {data[\"primary_reason\"]}')"

echo " B) Pooja Sharma acting as Maker at Delhi under cover grant:"
curl -s -X GET "${BASE_URL}/decide?user_id=pooja-sharma&action=prepare&job_id=JOB-SHOWCASE-03" \
  -H "X-User-Id: pooja-sharma" | python -c "import sys, json; data=json.load(sys.stdin); print(f'Pooja Allowed: {data[\"allowed\"]}, Grants Used: {data[\"matched_grants\"]}')"

echo -e "\n========================================================================"
echo " 5. EXPLAIN & COMPARE ('Why can Priya do this and Faisal cannot?')"
echo "========================================================================"
curl -s -X GET "${BASE_URL}/explain/compare?users=priya-nair,faisal-khan&action=check&job_id=JOB-SHOWCASE-01" \
  -H "X-User-Id: om-agrawal" | python -c "import sys, json; data=json.load(sys.stdin); print('SUMMARY: ' + data['comparison_summary'])"

echo -e "\n========================================================================"
echo " 6. HISTORICAL TIME-TRAVEL ('Who could have changed this on Oct 3rd?')"
echo "========================================================================"
curl -s -X GET "${BASE_URL}/jobs/JOB-HIST-DEMO-01/who-could?action=prepare&at=2026-10-03T14:00:00Z" \
  -H "X-User-Id: om-agrawal" | python -c "import sys, json; data=json.load(sys.stdin); print(f'Eligible Actors: {[a[\"name\"] for a in data[\"actors_who_could\"]]}'); print(f'Actual Actor: {data[\"actual_actor\"]}')"

echo -e "\n========================================================================"
echo " 7. CLIENT PRIVACY & REDACTION (RAJESH GUPTA - CLIENT C01)"
echo "========================================================================"
curl -s -X GET "${BASE_URL}/jobs/JOB-SHOWCASE-01" \
  -H "X-User-Id: rajesh-gupta" | python -m json.tool

echo -e "\n========================================================================"
echo " 8. TWO-PERSON APPROVAL FOR FILED SHIPMENTS"
echo " Sunita requests cancellation on FILED job NF-SHOWCASE-FILED"
echo "========================================================================"
curl -s -X POST "${BASE_URL}/jobs/JOB-SHOWCASE-01/actions/cancel_filed" \
  -H "X-User-Id: sunita-patil" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Client cancelled shipment after filing due to port strike"}' | python -m json.tool

echo -e "\n========================================================================"
echo " DEMO COMPLETED SUCCESSFULLY"
echo "========================================================================"
