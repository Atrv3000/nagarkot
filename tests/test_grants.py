"""Tests for grant management, self-escalation prevention, containment, and auto-unassignment."""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException

from app.models import User, Grant, Role, Job
from app.grants import create_grants, revoke_grant, describe_user_access
from app.schemas import GrantCreateItem


def test_self_grant_prohibited(db, seed_basic_catalogue):
    """Nobody can grant roles to themselves (self-escalation guard)."""
    now = seed_basic_catalogue["now"]
    super_admin = User(id="om-agrawal", name="Om", type="staff", status="active", created_at=now)
    db.add(super_admin)
    # Grant super admin
    grt = Grant(
        id="grt-om",
        user_id="om-agrawal",
        role_id="super_admin",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="bootstrap",
        created_at=now - timedelta(days=1),
        reason="Super Admin",
        batch_id="b0",
    )
    db.add(grt)
    db.commit()

    items = [
        GrantCreateItem(role_id="maker", effect="allow", reason="Self grant attempt")
    ]
    with pytest.raises(HTTPException) as exc_info:
        create_grants(db, grantor=super_admin, target_user_id="om-agrawal", items=items)

    assert exc_info.value.status_code == 403
    assert "Self-escalation violation" in exc_info.value.detail


def test_scope_containment_violation(db, seed_basic_catalogue):
    """Grantor cannot grant scope broader than their own access.manage scope."""
    now = seed_basic_catalogue["now"]
    deepak = User(id="deepak-verma", name="Deepak", type="staff", status="active", created_at=now)
    target = User(id="staff-target", name="Target Staff", type="staff", status="active", created_at=now)
    db.add_all([deepak, target])

    # Deepak holds access.manage restricted to Mumbai-Fort and Nhava Sheva only
    grt_deepak_mum = Grant(
        id="grt-deepak-mum",
        user_id="deepak-verma",
        role_id="access_admin",
        branch_id="BR-MUM",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="om-agrawal",
        created_at=now - timedelta(days=1),
        reason="Access admin Mumbai",
        batch_id="b1",
    )
    db.add(grt_deepak_mum)
    db.commit()

    # Deepak attempts to grant Chennai (outside his scope)
    items = [
        GrantCreateItem(role_id="maker", branch_id="BR-MAA", effect="allow", reason="Chennai maker")
    ]
    with pytest.raises(HTTPException) as exc_info:
        create_grants(db, grantor=deepak, target_user_id="staff-target", items=items)

    assert exc_info.value.status_code == 403
    assert "scope does not contain" in exc_info.value.detail

    # Deepak attempts to grant wildcard branch (all branches) -> also rejected
    items_all = [
        GrantCreateItem(role_id="maker", branch_id=None, effect="allow", reason="All branch maker")
    ]
    with pytest.raises(HTTPException) as exc_info_all:
        create_grants(db, grantor=deepak, target_user_id="staff-target", items=items_all)

    assert exc_info_all.value.status_code == 403


def test_privileged_role_denied_for_access_admin(db, seed_basic_catalogue):
    """Access Admin lacking access.manage_privileged cannot grant privileged roles (e.g. Approver, Super Admin)."""
    now = seed_basic_catalogue["now"]
    deepak = User(id="deepak-verma", name="Deepak", type="staff", status="active", created_at=now)
    target = User(id="staff-target", name="Target Staff", type="staff", status="active", created_at=now)
    db.add_all([deepak, target])

    # Access Admin holds access.manage, but NOT access.manage_privileged
    grt_deepak = Grant(
        id="grt-deepak-all",
        user_id="deepak-verma",
        role_id="access_admin",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="om-agrawal",
        created_at=now - timedelta(days=1),
        reason="Access Admin",
        batch_id="b1",
    )
    db.add(grt_deepak)
    db.commit()

    # Try granting 'approver' (contains job.approve_sensitive -> privileged)
    items = [
        GrantCreateItem(role_id="approver", effect="allow", reason="Make approver")
    ]
    with pytest.raises(HTTPException) as exc_info:
        create_grants(db, grantor=deepak, target_user_id="staff-target", items=items)

    assert exc_info.value.status_code == 403
    assert "privileged" in exc_info.value.detail


def test_self_revocation_denied(db, seed_basic_catalogue):
    """Nobody can revoke a grant for themselves."""
    now = seed_basic_catalogue["now"]
    user = User(id="deepak-verma", name="Deepak", type="staff", status="active", created_at=now)
    db.add(user)
    grt = Grant(
        id="grt-deepak",
        user_id="deepak-verma",
        role_id="access_admin",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="om-agrawal",
        created_at=now - timedelta(days=1),
        reason="Access Admin",
        batch_id="b1",
    )
    db.add(grt)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        revoke_grant(db, grantor=user, grant_id="grt-deepak", reason="Self revoke attempt")

    assert exc_info.value.status_code == 403
    assert "Self-escalation violation" in exc_info.value.detail


def test_lock_out_guard_last_super_admin(db, seed_basic_catalogue):
    """System prevents revoking the last active Super Admin grant."""
    now = seed_basic_catalogue["now"]
    om = User(id="om-agrawal", name="Om", type="staff", status="active", created_at=now)
    admin2 = User(id="admin-two", name="Admin Two", type="staff", status="active", created_at=now)
    db.add_all([om, admin2])

    grt_om = Grant(
        id="grt-om-sa",
        user_id="om-agrawal",
        role_id="super_admin",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="bootstrap",
        created_at=now - timedelta(days=1),
        reason="Sole Super Admin",
        batch_id="b1",
    )
    grt_admin2 = Grant(
        id="grt-admin2",
        user_id="admin-two",
        role_id="access_admin",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="om",
        created_at=now - timedelta(days=1),
        reason="Access Admin",
        batch_id="b2",
    )
    db.add_all([grt_om, grt_admin2])
    db.commit()

    # Admin 2 tries to revoke Om's grant (which is the last Super Admin grant)
    with pytest.raises(HTTPException) as exc_info:
        revoke_grant(db, grantor=admin2, grant_id="grt-om-sa", reason="Revoke last super admin")

    assert exc_info.value.status_code == 403
    assert "Lock-out guard" in exc_info.value.detail


def test_auto_unassign_on_grant_revocation(db, seed_basic_catalogue):
    """When a user's operational grant is revoked, assigned in-flight jobs are auto-unassigned."""
    now = seed_basic_catalogue["now"]
    om = User(id="om-agrawal", name="Om", type="staff", status="active", created_at=now)
    arjun = User(id="arjun-reddy", name="Arjun", type="staff", status="active", created_at=now)
    db.add_all([om, arjun])

    grt_om = Grant(
        id="grt-om-full",
        user_id="om-agrawal",
        role_id="super_admin",
        effect="allow",
        valid_from=now - timedelta(days=5),
        granted_by="bootstrap",
        created_at=now - timedelta(days=5),
        reason="Super Admin",
        batch_id="b0",
    )
    grt_arjun = Grant(
        id="grt-arjun-c08",
        user_id="arjun-reddy",
        role_id="checker",
        client_id="C08",
        effect="allow",
        valid_from=now - timedelta(days=5),
        granted_by="om-agrawal",
        created_at=now - timedelta(days=5),
        reason="Checker C08",
        batch_id="b1",
    )
    # Job assigned to Arjun waiting for Check
    job_c08 = Job(
        id="JOB-C08-INFLIGHT",
        ref="NF-C08-001",
        client_id="C08",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="PREPARED",
        assigned_to="arjun-reddy",
        created_by="someone",
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(days=1),
    )
    db.add_all([grt_om, grt_arjun, job_c08])
    db.commit()

    # Om revokes Arjun's grant
    revoke_grant(db, grantor=om, grant_id="grt-arjun-c08", reason="Reassigned territory")

    # Verify job is unassigned!
    db.refresh(job_c08)
    assert job_c08.assigned_to is None
