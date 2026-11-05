"""
Demo step verification as a proper pytest test using the seeded_client fixture.
This guarantees isolation - each test gets its own in-memory DB seeded from scratch.
Run with: pytest tests/test_demo_steps.py -v
"""
import pytest
from datetime import datetime, timezone


def test_01_health_check(seeded_client):
    r = seeded_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_02a_sod_conflict_asha_cannot_check_own_prepared_job(seeded_client):
    """Asha prepared JOB-SHOWCASE-02 (C03); SoD forbids her checking it."""
    r = seeded_client.get("/decide?user_id=asha-rao&action=check&job_id=JOB-SHOWCASE-02",
                          headers={"X-User-Id": "asha-rao"})
    assert r.status_code == 200
    d = r.json()
    assert not d["allowed"]
    assert d["primary_reason"] == "SOD_VIOLATION_MAKER_CHECKER"


def test_02b_sod_allowed_on_others_prepared_job(seeded_client):
    """Asha has Checker for C05; JOB-SHOWCASE-03 was prepared by Imran -> ALLOW."""
    r = seeded_client.get("/decide?user_id=asha-rao&action=check&job_id=JOB-SHOWCASE-03",
                          headers={"X-User-Id": "asha-rao"})
    assert r.status_code == 200
    d = r.json()
    assert d["allowed"], f"Expected ALLOW but got {d['primary_reason']}: {d}"
    assert d["outcome"] == "ALLOW"


def test_03a_rohit_allowed_in_scope(seeded_client):
    """Rohit's grant: C01/MUM/IMPORT/all-modes. JOB-SHOWCASE-05 matches exactly."""
    r = seeded_client.get("/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-05",
                          headers={"X-User-Id": "rohit-mehta"})
    assert r.status_code == 200
    d = r.json()
    assert d["allowed"], f"Expected ALLOW, got {d}"
    assert d["outcome"] == "ALLOW"


def test_03b_rohit_denied_export_mismatch(seeded_client):
    """JOB-SHOWCASE-06 is EXPORT; Rohit's grant is IMPORT only."""
    r = seeded_client.get("/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-06",
                          headers={"X-User-Id": "rohit-mehta"})
    d = r.json()
    assert not d["allowed"]
    assert d["primary_reason"] == "NO_GRANT"


def test_03c_rohit_denied_other_branch(seeded_client):
    """JOB-SHOWCASE-07 is Nhava Sheva; Rohit's grant is Mumbai-Fort only."""
    r = seeded_client.get("/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-07",
                          headers={"X-User-Id": "rohit-mehta"})
    d = r.json()
    assert not d["allowed"]
    assert d["primary_reason"] == "NO_GRANT"


def test_04_explain_compare_priya_vs_faisal(seeded_client):
    """Why can Priya check JOB-SHOWCASE-05 and Faisal can't?"""
    r = seeded_client.get(
        "/explain/compare?users=priya-nair,faisal-khan&action=check&job_id=JOB-SHOWCASE-05",
        headers={"X-User-Id": "om-agrawal"})
    assert r.status_code == 200
    summary = r.json()["comparison_summary"]
    assert "priya-nair" in summary
    assert "faisal-khan" in summary


def test_05a_absent_imran_denied(seeded_client):
    """JOB-SHOWCASE-08 is CONFIRMED; Imran is ABSENT -> USER_ABSENT."""
    r = seeded_client.get("/decide?user_id=imran-shaikh&action=prepare&job_id=JOB-SHOWCASE-08",
                          headers={"X-User-Id": "imran-shaikh"})
    d = r.json()
    assert not d["allowed"]
    assert d["primary_reason"] == "USER_ABSENT"


def test_05b_cover_grant_pooja_allowed(seeded_client):
    """Pooja has a 7-day cover grant as Maker for Delhi-ICD -> ALLOW on JOB-SHOWCASE-08."""
    r = seeded_client.get("/decide?user_id=pooja-sharma&action=prepare&job_id=JOB-SHOWCASE-08",
                          headers={"X-User-Id": "pooja-sharma"})
    d = r.json()
    assert d["allowed"], f"Expected ALLOW, got {d}"
    assert "grt-pooja-cover-imran" in d["matched_grants"]


def test_06a_cancel_filed_creates_pending_approval(seeded_client):
    """cancel_filed on FILED JOB-SHOWCASE-01 creates a pending approval (NEEDS_APPROVAL)."""
    r = seeded_client.post("/jobs/JOB-SHOWCASE-01/actions/cancel_filed",
                           headers={"X-User-Id": "sunita-patil"},
                           json={"reason": "Client cancelled after port strike"})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "NEEDS_APPROVAL"
    assert "approval_id" in d


def test_06b_self_approval_denied(seeded_client):
    """Requester of cancel_filed cannot approve their own request."""
    # First create the approval request
    r = seeded_client.post("/jobs/JOB-SHOWCASE-01/actions/cancel_filed",
                           headers={"X-User-Id": "sunita-patil"},
                           json={"reason": "Client cancelled after port strike"})
    assert r.status_code == 200
    approval_id = r.json()["approval_id"]

    r_self = seeded_client.post(f"/approvals/{approval_id}/approve",
                                headers={"X-User-Id": "sunita-patil"},
                                json={"reason": "Self approval attempt"})
    assert r_self.status_code == 403


def test_07_ops_admin_override_send_back(seeded_client):
    """Meera (Ops Admin) sends PREPARED JOB-SHOWCASE-03 back to CONFIRMED with reason."""
    r = seeded_client.post("/jobs/JOB-SHOWCASE-03/actions/override_send_back",
                           headers={"X-User-Id": "meera-iyer"},
                           json={"reason": "Shipment stalled due to preparer absence"})
    assert r.status_code == 200
    d = r.json()
    assert d["current_stage"] == "CONFIRMED"
    assert d["action"] == "override_send_back"


def test_08a_admin_self_grant_denied(seeded_client):
    """Nobody can grant themselves a role."""
    r = seeded_client.post("/grants",
                           headers={"X-User-Id": "deepak-verma"},
                           json={"user_id": "deepak-verma",
                                 "grants": [{"role_id": "maker", "branch_id": "BR-MUM", "effect": "allow",
                                             "reason": "Self-grant test"}]})
    assert r.status_code == 403


def test_08b_access_admin_cannot_grant_privileged_role(seeded_client):
    """Deepak (Access Admin, no access.manage_privileged) cannot grant Super Admin."""
    r = seeded_client.post("/grants",
                           headers={"X-User-Id": "deepak-verma"},
                           json={"user_id": "faisal-khan",
                                 "grants": [{"role_id": "super_admin", "branch_id": "BR-MUM", "effect": "allow",
                                             "reason": "Escalation test"}]})
    assert r.status_code == 403


def test_09_historical_time_travel_who_could(seeded_client):
    """Who could have prepared JOB-HIST-DEMO-01 on Oct 3rd?"""
    r = seeded_client.get(
        "/jobs/JOB-HIST-DEMO-01/who-could?action=prepare&at=2026-10-03T14:00:00Z",
        headers={"X-User-Id": "om-agrawal"})
    assert r.status_code == 200
    d = r.json()
    assert "actors_who_could" in d
    assert "actual_actor" in d


def test_10_job_history_has_events(seeded_client):
    """JOB-SHOWCASE-01 has an audit history."""
    r = seeded_client.get("/jobs/JOB-SHOWCASE-01/history",
                          headers={"X-User-Id": "meera-iyer"})
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_11_client_data_redaction(seeded_client):
    """Rajesh (C01 client user) sees only C01 jobs with internal fields redacted."""
    r = seeded_client.get("/jobs/JOB-SHOWCASE-01", headers={"X-User-Id": "rajesh-gupta"})
    assert r.status_code == 200
    d = r.json()
    assert d["client_id"] == "C01"
    assert d["internal_notes"] is None
    assert d["assigned_to"] is None
    assert d["prepared_by"] is None
    assert d["checked_by"] is None
    assert d["filed_by"] is None
