"""Tests for two-person approvals on sensitive actions (cancel_filed, reopen)."""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException

from app.models import User, Grant, Job, Approval
from app.jobs import execute_job_action
from app.approvals import approve_request, reject_request
from app.schemas import JobActionRequest


def test_cancel_filed_approval_workflow(db, seed_basic_catalogue):
    """cancel_filed requires 2-person approval; approver must differ from requester."""
    now = seed_basic_catalogue["now"]
    requester = User(id="sunita-patil", name="Sunita", type="staff", status="active", created_at=now)
    approver = User(id="approver-two", name="Approver Two", type="staff", status="active", created_at=now)
    db.add_all([requester, approver])

    g_req = Grant(
        id="g-req", user_id="sunita-patil", role_id="approver", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Approver", batch_id="b1"
    )
    g_app = Grant(
        id="g-app", user_id="approver-two", role_id="approver", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Approver", batch_id="b1"
    )
    db.add_all([g_req, g_app])

    job = Job(
        id="JOB-SENS-01",
        ref="NF-SENS-01",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="FILED",
        created_by="system",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    # 1. Requester submits cancel_filed action with reason
    res = execute_job_action(
        db, requester, job.id, "cancel_filed",
        JobActionRequest(reason="Shipper requested cancellation post-filing"),
    )
    assert res["status"] == "NEEDS_APPROVAL"
    approval_id = res["approval_id"]

    # 2. Requester tries to self-approve -> Fails with 403 (SoD violation)
    with pytest.raises(HTTPException) as exc_self:
        approve_request(db, approver=requester, approval_id=approval_id, reason="Approving my own request")
    assert exc_self.value.status_code == 403
    assert "Separation of duties" in exc_self.value.detail

    # 3. Second approver approves -> Succeeds and transitions job to CANCELLED
    approved_app = approve_request(db, approver=approver, approval_id=approval_id, reason="Verified shipper documentation")
    assert approved_app.status == "approved"
    db.refresh(job)
    assert job.stage == "CANCELLED"


def test_reopen_cycle_increment(db, seed_basic_catalogue):
    """Reopening a filed job increments cycle counter and resets workflow actors."""
    now = seed_basic_catalogue["now"]
    requester = User(id="sunita-patil", name="Sunita", type="staff", status="active", created_at=now)
    approver = User(id="approver-two", name="Approver Two", type="staff", status="active", created_at=now)
    db.add_all([requester, approver])

    g_req = Grant(
        id="g-req", user_id="sunita-patil", role_id="approver", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Approver", batch_id="b1"
    )
    g_app = Grant(
        id="g-app", user_id="approver-two", role_id="approver", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Approver", batch_id="b1"
    )
    db.add_all([g_req, g_app])

    job = Job(
        id="JOB-REOPEN-01",
        ref="NF-REOPEN-01",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="FILED",
        prepared_by="asha-rao",
        checked_by="priya-nair",
        filed_by="neha-kulkarni",
        cycle=1,
        created_by="system",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    # Request reopen
    res = execute_job_action(
        db, requester, job.id, "reopen",
        JobActionRequest(reason="Customs amendment required on filed entry"),
    )
    approval_id = res["approval_id"]

    # Approver approves
    approve_request(db, approver=approver, approval_id=approval_id, reason="Amendment approved by Customs")
    db.refresh(job)

    assert job.stage == "REOPENED"
    assert job.cycle == 2
    assert job.prepared_by is None
    assert job.checked_by is None
    assert job.filed_by is None


def test_stale_approval_fails_closed(db, seed_basic_catalogue):
    """If a job's stage changes before pending approval is decided, approval marks stale and fails closed."""
    now = seed_basic_catalogue["now"]
    requester = User(id="sunita-patil", name="Sunita", type="staff", status="active", created_at=now)
    approver = User(id="approver-two", name="Approver Two", type="staff", status="active", created_at=now)
    db.add_all([requester, approver])

    g_req = Grant(
        id="g-req", user_id="sunita-patil", role_id="approver", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Approver", batch_id="b1"
    )
    g_app = Grant(
        id="g-app", user_id="approver-two", role_id="approver", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="admin", created_at=now, reason="Approver", batch_id="b1"
    )
    db.add_all([g_req, g_app])

    job = Job(
        id="JOB-STALE-01",
        ref="NF-STALE-01",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="FILED",
        created_by="system",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    # Request cancel_filed
    res = execute_job_action(
        db, requester, job.id, "cancel_filed",
        JobActionRequest(reason="Shipper cancellation request"),
    )
    approval_id = res["approval_id"]

    # Concurrently job was changed to CANCELLED via another mechanism
    job.stage = "CANCELLED"
    db.commit()

    # Approver now tries to approve the cancel_filed request
    with pytest.raises(HTTPException) as exc_info:
        approve_request(db, approver=approver, approval_id=approval_id, reason="Late approval")

    assert exc_info.value.status_code == 409
    assert "STALE" in exc_info.value.detail

    # Verify approval status in DB is marked stale
    app_db = db.query(Approval).filter(Approval.id == approval_id).first()
    assert app_db.status == "stale"
