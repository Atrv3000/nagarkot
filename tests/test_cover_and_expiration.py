import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, Grant, Job
from app.decision import decide
from app.clock import get_now, set_time, reset_time
from datetime import datetime, timezone, timedelta


def test_cover_grant_active_only_when_covered_user_is_absent(seeded_client: TestClient, seeded_db: Session):
    """Pooja's cover grant for Imran is active ONLY while Imran is absent.
    If Imran returns to active status, Pooja's cover grant becomes inactive immediately.
    """
    imran = seeded_db.query(User).filter(User.id == "imran-shaikh").first()
    pooja = seeded_db.query(User).filter(User.id == "pooja-sharma").first()
    delhi_job = seeded_db.query(Job).filter(Job.id == "JOB-SHOWCASE-08").first()

    # Precondition: Imran is absent
    assert imran.status == "absent"

    # Pooja can prepare Delhi job under her cover grant
    dec = decide(seeded_db, user_id="pooja-sharma", action="prepare", job=delhi_job)
    assert dec.allowed is True
    assert "grt-pooja-cover-imran" in dec.matched_grants

    # Imran returns to work (status = active via official status update endpoint)
    r = seeded_client.patch(
        "/users/imran-shaikh/status",
        headers={"X-User-Id": "om-agrawal"},
        json={"status": "active", "reason": "Returned from medical leave"}
    )
    assert r.status_code == 200
    seeded_db.refresh(imran)
    assert imran.status == "active"

    # Now Pooja's cover grant is INACTIVE because Imran is no longer absent
    dec_after = decide(seeded_db, user_id="pooja-sharma", action="prepare", job=delhi_job)
    assert dec_after.allowed is False
    assert "grt-pooja-cover-imran" not in dec_after.matched_grants

    # Imran marks absent again -> Pooja's cover grant immediately reactivates
    r2 = seeded_client.patch(
        "/users/imran-shaikh/status",
        headers={"X-User-Id": "om-agrawal"},
        json={"status": "absent", "reason": "Sick again"}
    )
    assert r2.status_code == 200
    seeded_db.refresh(imran)
    assert imran.status == "absent"

    dec_rearmed = decide(seeded_db, user_id="pooja-sharma", action="prepare", job=delhi_job)
    assert dec_rearmed.allowed is True


def test_role_permission_removal_auto_unassigns_jobs(seeded_client: TestClient, seeded_db: Session):
    """When a role has permissions removed, users holding that role have in-flight jobs unassigned."""
    # Assign a PREPARED job to Rohit Mehta
    job = seeded_db.query(Job).filter(Job.id == "JOB-SHOWCASE-05").first()
    job.assigned_to = "rohit-mehta"
    seeded_db.commit()

    assert job.assigned_to == "rohit-mehta"

    # Remove 'job.check' from the 'checker' role as Super Admin
    r = seeded_client.put(
        "/roles/checker/permissions",
        headers={"X-User-Id": "om-agrawal"},
        json={"permissions": ["job.view", "job.view_internal"], "reason": "Temporarily suspend checking role"},
    )
    assert r.status_code == 200

    # Rohit's assigned job should now be auto-unassigned!
    seeded_db.refresh(job)
    assert job.assigned_to is None


def test_sweep_expired_grants_endpoint(seeded_client: TestClient, seeded_db: Session):
    """Calling /grants/sweep-expired unassigns jobs for users with expired grants."""
    r = seeded_client.post("/grants/sweep-expired", headers={"X-User-Id": "om-agrawal"})
    assert r.status_code == 200
    assert "unassigned_jobs_count" in r.json()

    # Unauthorized caller blocked
    r_unauth = seeded_client.post("/grants/sweep-expired", headers={"X-User-Id": "zoya-ansari"})
    assert r_unauth.status_code == 403
