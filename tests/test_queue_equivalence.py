"""Equivalence verification: SQL queue predicate vs Python decide() over all users and jobs."""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.models import User, Job, Grant
from app.clock import set_time, reset_time
from app.decision import decide
from app.scope import compile_my_queue_predicate


def _compute_expected_queue_for_user(db, user, jobs, absent_user_ids, at):
    """Compute the set of job IDs waiting for a user according to the Python decision engine."""
    expected_ids = set()
    if user.status != "active":
        return expected_ids

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
        decision = decide(db, user_id=user.id, action=next_action, job=job, at=at)
        if decision.allowed:
            expected_ids.add(job.id)

    return expected_ids


def test_queue_sql_python_equivalence_on_seeded_data(seeded_db):
    """For every seeded user, set of job IDs in /me/queue equals set obtained by running decide() in Python."""
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    set_time(now)

    users = seeded_db.query(User).all()
    jobs = seeded_db.query(Job).all()

    # Preconditions
    assert len(users) >= 20, f"Expected at least 20 seeded users, got {len(users)}"
    assert len(jobs) >= 300, f"Expected at least 300 seeded jobs, got {len(jobs)}"

    absent_user_ids = {u.id for u in users if u.status == "absent"}
    users_with_non_empty_queue = []

    for user in users:
        expected_ids = _compute_expected_queue_for_user(seeded_db, user, jobs, absent_user_ids, now)
        if len(expected_ids) > 0:
            users_with_non_empty_queue.append(user.id)

        # Query via SQL predicate
        predicate = compile_my_queue_predicate(seeded_db, user, now)
        actual_jobs = seeded_db.query(Job).filter(predicate).all()
        actual_ids = {j.id for j in actual_jobs}

        assert actual_ids == expected_ids, (
            f"Equivalence mismatch for user '{user.id}' ({user.name}): "
            f"SQL returned {len(actual_ids)} jobs, Python decide() expected {len(expected_ids)} jobs. "
            f"Difference: {actual_ids.symmetric_difference(expected_ids)}"
        )

    # Prove test cannot pass vacuously
    assert len(users_with_non_empty_queue) >= 5, (
        f"Expected at least 5 users with non-empty queue, got {len(users_with_non_empty_queue)}: "
        f"{users_with_non_empty_queue}"
    )


def test_api_queue_pagination_and_count_equivalence(seeded_client, seeded_db):
    """GET /me/queue returns exact Python-computed jobs across single-page and paginated queries."""
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    set_time(now)

    users = seeded_db.query(User).all()
    jobs = seeded_db.query(Job).all()
    absent_user_ids = {u.id for u in users if u.status == "absent"}

    test_personas = ["asha-rao", "pooja-sharma", "neha-kulkarni", "priya-nair"]
    for uid in test_personas:
        user = seeded_db.query(User).filter(User.id == uid).first()
        expected_ids = _compute_expected_queue_for_user(seeded_db, user, jobs, absent_user_ids, now)

        # 1. Single query with large limit
        resp = seeded_client.get("/me/queue?limit=200", headers={"X-User-Id": uid})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["count"] == len(data["items"])
        assert data["count"] == len(expected_ids)
        api_ids = {item["id"] for item in data["items"]}
        assert api_ids == expected_ids

        # 2. Walk all pages with small limit (keyset pagination)
        paged_ids = []
        cursor = None
        while True:
            params = {"limit": 7}
            if cursor:
                params["cursor"] = cursor
            page_resp = seeded_client.get("/me/queue", params=params, headers={"X-User-Id": uid})
            assert page_resp.status_code == 200
            page_data = page_resp.json()
            items = page_data["items"]
            paged_ids.extend([it["id"] for it in items])
            cursor = page_data.get("next_cursor")
            if not cursor:
                break

        # Verify no duplicates and full union matches
        assert len(paged_ids) == len(set(paged_ids)), f"Duplicate items in pagination for {uid}"
        assert set(paged_ids) == expected_ids


def test_queue_negative_control_immediate_effect(seeded_client, seeded_db):
    """Negative control: revoking a grant immediately alters /me/queue and matches Python decide()."""
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    set_time(now)

    user = seeded_db.query(User).filter(User.id == "neha-kulkarni").first()
    jobs = seeded_db.query(Job).all()
    absent_user_ids = {u.id for u in seeded_db.query(User).all() if u.status == "absent"}

    initial_expected = _compute_expected_queue_for_user(seeded_db, user, jobs, absent_user_ids, now)
    assert len(initial_expected) > 0

    # Revoke Neha's Mumbai grant
    grant_mum = seeded_db.query(Grant).filter(
        Grant.user_id == "neha-kulkarni",
        Grant.branch_id == "BR-MUM"
    ).first()
    assert grant_mum is not None
    grant_mum.revoked_at = now
    grant_mum.revoked_by = "om-agrawal"
    seeded_db.commit()

    # Re-evaluate in Python
    updated_expected = _compute_expected_queue_for_user(seeded_db, user, jobs, absent_user_ids, now)
    assert len(updated_expected) < len(initial_expected), "Revocation should have reduced queue size"

    # API call to verify immediate effect
    resp = seeded_client.get("/me/queue?limit=200", headers={"X-User-Id": "neha-kulkarni"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == len(updated_expected)
    assert {it["id"] for it in data["items"]} == updated_expected

    # Also test marking user absent immediately clears queue
    user.status = "absent"
    seeded_db.commit()
    absent_expected = _compute_expected_queue_for_user(seeded_db, user, jobs, absent_user_ids, now)
    assert len(absent_expected) == 0

    resp_absent = seeded_client.get("/me/queue?limit=200", headers={"X-User-Id": "neha-kulkarni"})
    assert resp_absent.status_code == 200
    assert resp_absent.json()["count"] == 0
    assert len(resp_absent.json()["items"]) == 0
