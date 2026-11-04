"""Tests verifying zero-trust fail-closed behavior on anomalies and exceptions."""
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import patch

from app.models import User, Grant
from app.decision import decide


def test_indeterminate_exception_fails_closed(db, seed_basic_catalogue):
    """Any unexpected exception inside the decision engine returns DENY with INDETERMINATE."""
    now = seed_basic_catalogue["now"]
    user = User(id="test-user", name="Test User", type="staff", status="active", created_at=now)
    db.add(user)
    db.commit()

    job_data = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "CONFIRMED",
    }

    # Force an unexpected exception during grant query
    with patch.object(db, "query", side_effect=RuntimeError("Simulated database failure")):
        decision = decide(db, user_id="test-user", action="prepare", job=job_data)

    assert not decision.allowed
    assert decision.outcome == "DENY"
    assert decision.primary_reason == "INDETERMINATE"
    assert any(c.code == "ENGINE_INTERNAL" and not c.passed for c in decision.checks)


def test_as_of_time_travel_reconstructs_past_state(db, seed_basic_catalogue):
    """Historical as-of query reproduces decision when user held valid grant before revocation."""
    t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)  # Grant revoked
    t2 = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    user = User(id="past-maker", name="Past Maker", type="staff", status="active", created_at=t0)
    db.add(user)
    # Grant active from t0 until revoked at t1
    grant = Grant(
        id="grt-past",
        user_id="past-maker",
        role_id="maker",
        effect="allow",
        valid_from=t0,
        granted_by="admin",
        created_at=t0,
        revoked_at=t1,
        revoked_by="admin",
        reason="Revoked on Oct 15",
        batch_id="b1",
    )
    db.add(grant)
    db.commit()

    job_data = {
        "client_id": "C01",
        "branch_id": "BR-MUM",
        "direction": "IMPORT",
        "mode": "AIR",
        "stage": "CONFIRMED",
    }

    # At t0 + 5 days: user was authorized!
    past_eval_time = t0 + timedelta(days=5)
    dec_past = decide(db, user_id="past-maker", action="prepare", job=job_data, at=past_eval_time)
    assert dec_past.allowed
    assert dec_past.outcome == "ALLOW"
    assert "grt-past" in dec_past.matched_grants

    # At t2 (today): user is denied!
    dec_now = decide(db, user_id="past-maker", action="prepare", job=job_data, at=t2)
    assert not dec_now.allowed
    assert dec_now.outcome == "DENY"
    assert dec_now.primary_reason == "NO_GRANT"
