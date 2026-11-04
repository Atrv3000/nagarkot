"""Unit tests for the 8-stage decision engine."""
import pytest
from datetime import datetime, timezone, timedelta

from app.clock import set_time
from app.decision import decide, explain_compare
from app.models import User, Grant, Job, AuditLog


def test_user_unknown(db, seed_basic_catalogue):
    """Unknown user returns USER_UNKNOWN primary reason and DENY outcome."""
    job_data = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "CONFIRMED",
    }
    decision = decide(db, user_id="nonexistent-user", action="prepare", job=job_data)
    assert not decision.allowed
    assert decision.outcome == "DENY"
    assert decision.primary_reason == "USER_UNKNOWN"
    assert any(c.code == "USER_KNOWN" and not c.passed for c in decision.checks)


def test_client_user_restricted_to_view(db, seed_basic_catalogue):
    """Client users cannot perform active operational actions like prepare."""
    now = seed_basic_catalogue["now"]
    client_user = User(id="client-rajesh", name="Rajesh", type="client", status="active", client_id="C01", created_at=now)
    db.add(client_user)
    db.commit()

    job_data = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "CONFIRMED",
    }
    decision = decide(db, user_id="client-rajesh", action="prepare", job=job_data)
    assert not decision.allowed
    assert decision.outcome == "DENY"
    assert decision.primary_reason == "CLIENT_USER_RESTRICTED"


def test_system_user_restricted(db, seed_basic_catalogue):
    """System users (e.g. parser) cannot advance stages (e.g. check or file)."""
    now = seed_basic_catalogue["now"]
    sys_user = User(id="parser-bot", name="Parser Bot", type="system", status="active", created_at=now)
    db.add(sys_user)
    db.commit()

    job_data = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "PREPARED",
    }
    decision = decide(db, user_id="parser-bot", action="check", job=job_data)
    assert not decision.allowed
    assert decision.primary_reason == "SYSTEM_USER_RESTRICTED"


def test_absent_user_cannot_act_but_can_view(db, seed_basic_catalogue):
    """Absent user cannot act on jobs, but retains read view."""
    now = seed_basic_catalogue["now"]
    user = User(id="imran-shaikh", name="Imran", type="staff", status="absent", created_at=now)
    db.add(user)
    # Give user maker grant
    grant = Grant(
        id="grt-imran",
        user_id="imran-shaikh",
        role_id="maker",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="admin",
        created_at=now - timedelta(days=1),
        reason="Assigned to Delhi",
        batch_id="b1",
    )
    db.add(grant)
    db.commit()

    job_data = {
        "client_id": "C01",
        "branch_id": "BR-DEL",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "CONFIRMED",
    }

    # Action prepare fails with USER_ABSENT
    act_decision = decide(db, user_id="imran-shaikh", action="prepare", job=job_data)
    assert not act_decision.allowed
    assert act_decision.primary_reason == "USER_ABSENT"

    # Action view is allowed
    view_decision = decide(db, user_id="imran-shaikh", action="view", job=job_data)
    assert view_decision.allowed
    assert view_decision.outcome == "ALLOW"


def test_incomplete_job_data(db, seed_basic_catalogue):
    """Missing or invalid dimensions on a job return JOB_INCOMPLETE."""
    now = seed_basic_catalogue["now"]
    user = User(id="asha-rao", name="Asha", type="staff", status="active", created_at=now)
    db.add(user)
    db.commit()

    # Missing branch_id and invalid direction
    job_bad = {
        "client_id": "C01",
        "direction": "INVALID_DIR",
        "mode": "AIR",
        "stage": "CONFIRMED",
    }
    decision = decide(db, user_id="asha-rao", action="prepare", job=job_bad)
    assert not decision.allowed
    assert decision.primary_reason == "JOB_INCOMPLETE"


def test_unknown_action(db, seed_basic_catalogue):
    """Unrecognized action returns ACTION_UNKNOWN."""
    now = seed_basic_catalogue["now"]
    user = User(id="asha-rao", name="Asha", type="staff", status="active", created_at=now)
    db.add(user)
    db.commit()

    job_data = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "CONFIRMED",
    }
    decision = decide(db, user_id="asha-rao", action="destroy_shipment", job=job_data)
    assert not decision.allowed
    assert decision.primary_reason == "ACTION_UNKNOWN"


def test_stage_invalid(db, seed_basic_catalogue):
    """Attempting prepare on a FILED job fails STAGE_INVALID."""
    now = seed_basic_catalogue["now"]
    user = User(id="asha-rao", name="Asha", type="staff", status="active", created_at=now)
    db.add(user)
    grant = Grant(
        id="grt-asha",
        user_id="asha-rao",
        role_id="maker",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="admin",
        created_at=now - timedelta(days=1),
        reason="Maker everywhere",
        batch_id="b1",
    )
    db.add(grant)
    db.commit()

    job_data = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "FILED",  # Already filed
    }
    decision = decide(db, user_id="asha-rao", action="prepare", job=job_data)
    assert not decision.allowed
    assert decision.primary_reason == "STAGE_INVALID"


def test_grant_covers_scope_and_deny_precedence(db, seed_basic_catalogue):
    """Explicit deny grant unconditionally overrides allow grant."""
    now = seed_basic_catalogue["now"]
    user = User(id="tarun-das", name="Tarun", type="staff", status="active", created_at=now)
    db.add(user)

    # Allow grant for Kolkata branch
    allow_grt = Grant(
        id="grt-tarun-allow",
        user_id="tarun-das",
        role_id="maker",
        branch_id="BR-CCU",
        effect="allow",
        valid_from=now - timedelta(days=5),
        granted_by="admin",
        created_at=now - timedelta(days=5),
        reason="Maker at Kolkata",
        batch_id="b1",
    )
    # Deny grant for client C04
    deny_grt = Grant(
        id="grt-tarun-deny",
        user_id="tarun-das",
        role_id="maker",
        client_id="C04",
        effect="deny",
        valid_from=now - timedelta(days=5),
        granted_by="admin",
        created_at=now - timedelta(days=5),
        reason="Conflict of interest with C04",
        batch_id="b2",
    )
    db.add_all([allow_grt, deny_grt])
    db.commit()

    # Job at Kolkata for C01 -> ALLOWED
    job_c01 = {
        "client_id": "C01",
        "branch_id": "BR-CCU",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "CONFIRMED",
    }
    dec_c01 = decide(db, user_id="tarun-das", action="prepare", job=job_c01)
    assert dec_c01.allowed
    assert dec_c01.outcome == "ALLOW"
    assert "grt-tarun-allow" in dec_c01.matched_grants

    # Job at Kolkata for C04 -> DENIED with EXPLICIT_DENY
    job_c04 = {
        "client_id": "C04",
        "branch_id": "BR-CCU",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "CONFIRMED",
    }
    dec_c04 = decide(db, user_id="tarun-das", action="prepare", job=job_c04)
    assert not dec_c04.allowed
    assert dec_c04.primary_reason == "EXPLICIT_DENY"
    assert "grt-tarun-deny" in dec_c04.denying_grants


def test_maker_checker_sod_conflict(db, seed_basic_catalogue):
    """User who prepared a job cannot check it in the current cycle."""
    now = seed_basic_catalogue["now"]
    user = User(id="karan-shah", name="Karan", type="staff", status="active", created_at=now)
    db.add(user)
    # Karan holds both Maker and Checker roles for Chennai / C02
    grt_maker = Grant(
        id="grt-karan-maker",
        user_id="karan-shah",
        role_id="maker",
        client_id="C02",
        branch_id="BR-MAA",
        effect="allow",
        valid_from=now - timedelta(days=5),
        granted_by="admin",
        created_at=now - timedelta(days=5),
        reason="Maker C02",
        batch_id="b1",
    )
    grt_checker = Grant(
        id="grt-karan-checker",
        user_id="karan-shah",
        role_id="checker",
        client_id="C02",
        branch_id="BR-MAA",
        effect="allow",
        valid_from=now - timedelta(days=5),
        granted_by="admin",
        created_at=now - timedelta(days=5),
        reason="Checker C02",
        batch_id="b1",
    )
    db.add_all([grt_maker, grt_checker])
    db.commit()

    # Job prepared by Karan
    job_prepared_by_karan = {
        "client_id": "C02",
        "branch_id": "BR-MAA",
        "direction": "EXPORT",
        "mode": "FCL",
        "stage": "PREPARED",
        "prepared_by": "karan-shah",
        "cycle": 1,
    }

    decision = decide(db, user_id="karan-shah", action="check", job=job_prepared_by_karan)
    assert not decision.allowed
    assert decision.primary_reason == "SOD_VIOLATION_MAKER_CHECKER"
    assert any(c.code == "SOD_OK" and not c.passed for c in decision.checks)


def test_sensitive_action_requires_reason_and_returns_needs_approval(db, seed_basic_catalogue):
    """cancel_filed on FILED job returns NEEDS_APPROVAL when authorized, and requires reason."""
    now = seed_basic_catalogue["now"]
    user = User(id="sunita-patil", name="Sunita", type="staff", status="active", created_at=now)
    db.add(user)
    grant = Grant(
        id="grt-sunita",
        user_id="sunita-patil",
        role_id="approver",
        effect="allow",
        valid_from=now - timedelta(days=5),
        granted_by="admin",
        created_at=now - timedelta(days=5),
        reason="Approver",
        batch_id="b1",
    )
    db.add(grant)
    db.commit()

    job_filed = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "FILED",
    }

    # Without reason -> fails REASON_REQUIRED
    dec_no_reason = decide(db, user_id="sunita-patil", action="cancel_filed", job=job_filed, reason="")
    assert not dec_no_reason.allowed
    assert dec_no_reason.primary_reason == "REASON_REQUIRED"

    # With reason -> NEEDS_APPROVAL
    dec_with_reason = decide(db, user_id="sunita-patil", action="cancel_filed", job=job_filed, reason="Client recalled cargo")
    assert dec_with_reason.allowed
    assert dec_with_reason.outcome == "NEEDS_APPROVAL"
    assert dec_with_reason.primary_reason is None


def test_explain_compare_output(db, seed_basic_catalogue):
    """explain_compare outputs clear human explanation contrasting two users."""
    now = seed_basic_catalogue["now"]
    user_a = User(id="priya-nair", name="Priya", type="staff", status="active", created_at=now)
    user_b = User(id="faisal-khan", name="Faisal", type="staff", status="active", created_at=now)
    db.add_all([user_a, user_b])

    grt_priya = Grant(
        id="grt-priya",
        user_id="priya-nair",
        role_id="checker",
        effect="allow",
        valid_from=now - timedelta(days=5),
        granted_by="admin",
        created_at=now - timedelta(days=5),
        reason="Checker everywhere",
        batch_id="b1",
    )
    grt_faisal = Grant(
        id="grt-faisal",
        user_id="faisal-khan",
        role_id="viewer",
        effect="allow",
        valid_from=now - timedelta(days=5),
        granted_by="admin",
        created_at=now - timedelta(days=5),
        reason="Viewer only",
        batch_id="b2",
    )
    db.add_all([grt_priya, grt_faisal])
    db.commit()

    job_data = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "PREPARED",
        "prepared_by": "someone-else",
    }

    dec_a = decide(db, "priya-nair", "check", job_data)
    dec_b = decide(db, "faisal-khan", "check", job_data)

    summary = explain_compare(dec_a, dec_b, "priya-nair", "faisal-khan")
    assert "priya-nair" in summary and "ALLOWED" in summary
    assert "faisal-khan" in summary and "DENIED" in summary
