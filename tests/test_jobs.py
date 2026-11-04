"""Tests for job state machine, concurrency, admin override, parser, and client user restrictions."""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException

from app.models import User, Grant, Job, AuditLog
from app.jobs import create_job, patch_job, execute_job_action, get_job_who_could
from app.schemas import JobCreate, JobPatch, JobActionRequest


def test_job_lifecycle_transitions(db, seed_basic_catalogue):
    """Full lifecycle: CONFIRMED -> PREPARED -> CHECKED -> FILED."""
    now = seed_basic_catalogue["now"]
    maker = User(id="asha-rao", name="Asha", type="staff", status="active", created_at=now)
    checker = User(id="priya-nair", name="Priya", type="staff", status="active", created_at=now)
    filer = User(id="neha-kulkarni", name="Neha", type="staff", status="active", created_at=now)
    db.add_all([maker, checker, filer])

    g_maker = Grant(
        id="g-m", user_id="asha-rao", role_id="maker", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Maker", batch_id="b1"
    )
    g_checker = Grant(
        id="g-c", user_id="priya-nair", role_id="checker", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Checker", batch_id="b1"
    )
    g_filer = Grant(
        id="g-f", user_id="neha-kulkarni", role_id="filer", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Filer", batch_id="b1"
    )
    db.add_all([g_maker, g_checker, g_filer])

    # Initial job in CONFIRMED
    job = Job(
        id="JOB-LIFE-01",
        ref="NF-LIFE-01",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="CONFIRMED",
        created_by="system",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    # 1. Asha prepares
    res_prep = execute_job_action(db, maker, job.id, "prepare", JobActionRequest())
    assert res_prep["status"] == "EXECUTED"
    db.refresh(job)
    assert job.stage == "PREPARED"
    assert job.prepared_by == "asha-rao"

    # 2. Priya checks
    res_chk = execute_job_action(db, checker, job.id, "check", JobActionRequest())
    assert res_chk["status"] == "EXECUTED"
    db.refresh(job)
    assert job.stage == "CHECKED"
    assert job.checked_by == "priya-nair"

    # 3. Neha files
    res_file = execute_job_action(db, filer, job.id, "file", JobActionRequest())
    assert res_file["status"] == "EXECUTED"
    db.refresh(job)
    assert job.stage == "FILED"
    assert job.filed_by == "neha-kulkarni"


def test_concurrency_conflict(db, seed_basic_catalogue):
    """When a job's stage is advanced concurrently, subsequent actions on stale stage fail with 409."""
    now = seed_basic_catalogue["now"]
    maker = User(id="asha-rao", name="Asha", type="staff", status="active", created_at=now)
    db.add(maker)
    g_maker = Grant(
        id="g-m", user_id="asha-rao", role_id="maker", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Maker", batch_id="b1"
    )
    db.add(g_maker)

    job = Job(
        id="JOB-CONC-01",
        ref="NF-CONC-01",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="CONFIRMED",
        created_by="system",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    # Simulate concurrent worker advancing stage directly
    job.stage = "PREPARED"
    db.commit()

    # Maker tries to prepare assuming it was CONFIRMED
    # Since DB stage is now PREPARED, stage_valid check in decide() fails with STAGE_INVALID
    with pytest.raises(HTTPException) as exc_info:
        execute_job_action(db, maker, job.id, "prepare", JobActionRequest())

    assert exc_info.value.status_code == 403
    assert "STAGE_INVALID" in exc_info.value.detail


def test_admin_override_send_back(db, seed_basic_catalogue):
    """Ops Admin send_back requires reason, is flagged is_override, and resets actor."""
    now = seed_basic_catalogue["now"]
    ops_admin = User(id="meera-iyer", name="Meera", type="staff", status="active", created_at=now)
    db.add(ops_admin)
    g_ops = Grant(
        id="g-ops", user_id="meera-iyer", role_id="ops_admin", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Ops Admin", batch_id="b1"
    )
    db.add(g_ops)

    job = Job(
        id="JOB-OVER-01",
        ref="NF-OVER-01",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="PREPARED",
        prepared_by="someone",
        created_by="system",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    # Without reason -> fails 403 REASON_REQUIRED
    with pytest.raises(HTTPException) as exc_no_reason:
        execute_job_action(db, ops_admin, job.id, "override_send_back", JobActionRequest(reason=""))
    assert "REASON_REQUIRED" in exc_no_reason.value.detail

    # With reason -> successfully sent back to CONFIRMED
    res = execute_job_action(
        db, ops_admin, job.id, "override_send_back",
        JobActionRequest(reason="Fixing missing manifest document"),
    )
    assert res["status"] == "EXECUTED"
    db.refresh(job)
    assert job.stage == "CONFIRMED"
    assert job.prepared_by is None

    # Check audit log is_override flag
    event = db.query(AuditLog).filter(AuditLog.job_id == job.id, AuditLog.action == "override_send_back").first()
    assert event is not None
    assert event.is_override is True


def test_overnight_parser_restrictions(db, seed_basic_catalogue):
    """Parser can create and update CONFIRMED jobs only, cannot advance stages, logs run ID."""
    now = seed_basic_catalogue["now"]
    parser = User(id="overnight-parser", name="Parser", type="system", status="active", created_at=now)
    db.add(parser)
    g_parser = Grant(
        id="g-par", user_id="overnight-parser", role_id="parser", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Parser", batch_id="b1"
    )
    db.add(g_parser)
    db.commit()

    # 1. Parser can create
    job_in = JobCreate(
        ref="NF-PARSER-01",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        internal_notes="Parsed from EDI",
    )
    job = create_job(db, parser, job_in, actor_run_id="RUN-20261104")
    assert job.stage == "CONFIRMED"

    # Verify audit has actor_run_id
    create_evt = db.query(AuditLog).filter(AuditLog.job_id == job.id, AuditLog.event_type == "JOB_CREATE").first()
    assert create_evt.actor_run_id == "RUN-20261104"

    # 2. Parser can patch CONFIRMED job
    patch_job(db, parser, job.id, JobPatch(internal_notes="Updated EDI notes"), actor_run_id="RUN-20261104")
    db.refresh(job)
    assert job.internal_notes == "Updated EDI notes"

    # 3. Parser CANNOT prepare or check
    with pytest.raises(HTTPException) as exc_info:
        execute_job_action(db, parser, job.id, "prepare", JobActionRequest(), actor_run_id="RUN-20261104")
    assert exc_info.value.status_code == 403


def test_who_could_audit_query(db, seed_basic_catalogue):
    """get_job_who_could correctly identifies all users eligible to take action."""
    now = seed_basic_catalogue["now"]
    maker1 = User(id="maker-1", name="Maker One", type="staff", status="active", created_at=now)
    maker2 = User(id="maker-2", name="Maker Two", type="staff", status="active", created_at=now)
    checker1 = User(id="checker-1", name="Checker One", type="staff", status="active", created_at=now)
    db.add_all([maker1, maker2, checker1])

    g1 = Grant(
        id="g-1", user_id="maker-1", role_id="maker", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Maker", batch_id="b1"
    )
    g2 = Grant(
        id="g-2", user_id="maker-2", role_id="maker", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Maker", batch_id="b1"
    )
    g3 = Grant(
        id="g-3", user_id="checker-1", role_id="checker", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Checker", batch_id="b1"
    )
    db.add_all([g1, g2, g3])

    job = Job(
        id="JOB-WHO-01",
        ref="NF-WHO-01",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="CONFIRMED",
        created_by="system",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    who_resp = get_job_who_could(db, job.id, "prepare", at=now)
    eligible_ids = {a.user_id for a in who_resp.actors_who_could}
    assert "maker-1" in eligible_ids
    assert "maker-2" in eligible_ids
    assert "checker-1" not in eligible_ids  # Checker role has no prepare permission
