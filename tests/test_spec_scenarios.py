"""Verification tests for specific core scenarios enumerated in the prompt."""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models import User, Grant, Job
from app.decision import decide
from app.jobs import execute_job_action
from app.schemas import JobActionRequest


def test_narrow_scope_checker_rohit(db, seed_basic_catalogue):
    """Rohit Mehta is allowed on C01/Mumbai-Fort/IMPORT, but denied on export, other branch, and other client."""
    now = seed_basic_catalogue["now"]
    rohit = User(id="rohit-mehta", name="Rohit", type="staff", status="active", created_at=now)
    db.add(rohit)
    g_rohit = Grant(
        id="grt-rohit-chk",
        user_id="rohit-mehta",
        role_id="checker",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode=None,  # All modes
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="admin",
        created_at=now - timedelta(days=1),
        reason="Mumbai Fort import checker for C01",
        batch_id="b-rohit",
    )
    db.add(g_rohit)
    db.commit()

    # Allowed: C01, BR-MUM, IMPORT, AIR, PREPARED
    job_ok = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "PREPARED",
        "prepared_by": "someone-else",
    }
    dec_ok = decide(db, user_id="rohit-mehta", action="check", job=job_ok)
    assert dec_ok.allowed
    assert dec_ok.outcome == "ALLOW"

    # Denied: EXPORT
    job_export = dict(job_ok, direction="EXPORT")
    dec_exp = decide(db, user_id="rohit-mehta", action="check", job=job_export)
    assert not dec_exp.allowed
    assert dec_exp.primary_reason == "NO_GRANT"

    # Denied: Other branch (Chennai)
    job_branch = dict(job_ok, branch_id="BR-MAA")
    dec_br = decide(db, user_id="rohit-mehta", action="check", job=job_branch)
    assert not dec_br.allowed
    assert dec_br.primary_reason == "NO_GRANT"

    # Denied: Other client (C02)
    job_client = dict(job_ok, client_id="C02")
    dec_cl = decide(db, user_id="rohit-mehta", action="check", job=job_client)
    assert not dec_cl.allowed
    assert dec_cl.primary_reason == "NO_GRANT"


def test_cover_grant_activation_and_expiration(db, seed_basic_catalogue):
    """Pooja's 7-day cover grant for Imran works during validity window, and expires after valid_to."""
    t_start = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
    t_end = datetime(2026, 11, 8, 0, 0, 0, tzinfo=timezone.utc)

    pooja = User(id="pooja-sharma", name="Pooja", type="staff", status="active", created_at=t_start)
    db.add(pooja)
    cover_grant = Grant(
        id="grt-pooja-cover",
        user_id="pooja-sharma",
        role_id="maker",
        branch_id="BR-DEL",
        effect="allow",
        valid_from=t_start,
        valid_to=t_end,
        granted_by="om-agrawal",
        created_at=t_start,
        reason="7-day cover for Imran",
        cover_for_user_id="imran-shaikh",
        batch_id="b-cover",
    )
    db.add(cover_grant)
    db.commit()

    delhi_job = {
        "client_id": "C01",
        "branch_id": "BR-DEL",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "CONFIRMED",
    }

    # During coverage (Nov 4): ALLOWED
    dec_active = decide(db, user_id="pooja-sharma", action="prepare", job=delhi_job, at=datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc))
    assert dec_active.allowed
    assert dec_active.outcome == "ALLOW"
    assert "grt-pooja-cover" in dec_active.matched_grants

    # After coverage expired (Nov 10): DENIED
    dec_expired = decide(db, user_id="pooja-sharma", action="prepare", job=delhi_job, at=datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc))
    assert not dec_expired.allowed
    assert dec_expired.primary_reason == "NO_GRANT"


def test_ops_admin_override_cannot_bypass_sod_or_touch_filed_without_approval(db, seed_basic_catalogue):
    """Admin override (job.override) CAN NEVER bypass SoD or act on FILED jobs without two-person approval."""
    now = seed_basic_catalogue["now"]
    meera = User(id="meera-iyer", name="Meera", type="staff", status="active", created_at=now)
    db.add(meera)
    g_meera = Grant(
        id="grt-meera", user_id="meera-iyer", role_id="ops_admin", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Ops Admin", batch_id="b1"
    )
    db.add(g_meera)

    # 1. Ops admin cannot touch FILED job via override_send_back
    job_filed = Job(
        id="JOB-FILED-OPS",
        ref="NF-FILED-OPS",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="FILED",
        created_by="system",
        created_at=now,
        updated_at=now,
    )
    db.add(job_filed)
    db.commit()

    with pytest.raises(HTTPException) as exc_filed:
        execute_job_action(db, meera, job_filed.id, "override_send_back", JobActionRequest(reason="Trying to roll back filed"))
    assert exc_filed.value.status_code == 403
    assert "STAGE_INVALID" in exc_filed.value.detail

    # 2. Ops admin cannot check a job they prepared (SoD is unbreakable)
    job_prepared_by_meera = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "PREPARED",
        "prepared_by": "meera-iyer",
    }
    dec_sod = decide(db, user_id="meera-iyer", action="check", job=job_prepared_by_meera)
    assert not dec_sod.allowed
    assert any(c.code == "SOD_OK" and not c.passed for c in dec_sod.checks)


def test_client_user_redaction_and_isolation(db, seed_basic_catalogue):
    """Client user only sees their own client's shipments and internal fields are redacted."""
    client = TestClient(app)
    headers = {"X-User-Id": "rajesh-gupta"}

    resp = client.get("/jobs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        # Only client C01
        assert item["client_id"] == "C01"
        # Internal fields redacted
        assert item["internal_notes"] is None
        assert item["assigned_to"] is None
        assert item["prepared_by"] is None
        assert item["checked_by"] is None
        assert item["filed_by"] is None
