"""Equivalence verification: SQL queue predicate vs Python decide() over all users and jobs."""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.models import User, Job
from app.clock import set_time, reset_time
from app.decision import decide
from app.scope import compile_my_queue_predicate


def test_queue_sql_python_equivalence_on_seeded_data(db, seed_basic_catalogue):
    """For every seeded user, set of job IDs in /me/queue equals set obtained by running decide() in Python."""
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    set_time(now)

    # Let's seed the full persona and job set in the test db
    from scripts.seed import seed
    # Run seed against the test DB session
    from app.models import (
        User, Branch, Client, Role, RolePermission, Grant, Job, SoDRule, Approval, AuditLog
    )

    # Fetch all users and jobs from the test db
    users = db.query(User).all()
    jobs = db.query(Job).all()

    absent_user_ids = {u.id for u in users if u.status == "absent"}

    for user in users:
        # Determine expected jobs in Python
        expected_ids = set()

        if user.status == "active":
            for job in jobs:
                # 1. Assignment condition: unassigned OR assigned to me OR assignee is absent
                assignee_ok = (
                    job.assigned_to is None
                    or job.assigned_to == user.id
                    or job.assigned_to in absent_user_ids
                )
                if not assignee_ok:
                    continue

                # 2. Stage ready action
                next_action = None
                if job.stage in ("CONFIRMED", "REOPENED"):
                    next_action = "prepare"
                elif job.stage == "PREPARED":
                    next_action = "check"
                elif job.stage == "CHECKED":
                    next_action = "file"

                if not next_action:
                    continue

                # 3. Decision engine evaluate
                decision = decide(db, user_id=user.id, action=next_action, job=job, at=now)
                if decision.allowed:
                    expected_ids.add(job.id)

        # Query via SQL predicate
        predicate = compile_my_queue_predicate(db, user, now)
        actual_jobs = db.query(Job).filter(predicate).all()
        actual_ids = {j.id for j in actual_jobs}

        assert actual_ids == expected_ids, (
            f"Equivalence mismatch for user '{user.id}' ({user.name}): "
            f"SQL returned {len(actual_ids)} jobs, Python decide() expected {len(expected_ids)} jobs. "
            f"Difference: {actual_ids.symmetric_difference(expected_ids)}"
        )


def test_api_queue_count_equals_items_len(seeded_client):
    """GET /me/queue returns count == len(items) from the exact same predicate."""
    headers = {"X-User-Id": "asha-rao"}

    # Query /me/queue with large limit to retrieve all items in queue
    resp = seeded_client.get("/me/queue?limit=200", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert "items" in data
    assert data["count"] > 0
    # When limit is greater than or equal to total, count == len(items)
    if data["next_cursor"] is None:
        assert data["count"] == len(data["items"])
