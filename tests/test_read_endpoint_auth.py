import pytest
from starlette.testclient import TestClient


def test_unauthorized_user_grants_access_blocked(seeded_client: TestClient):
    """Zoya (no grants) and Rajesh (client user) cannot inspect Om's grants or access summary."""
    # Zoya cannot view Om's grants
    r = seeded_client.get("/users/om-agrawal/grants", headers={"X-User-Id": "zoya-ansari"})
    assert r.status_code == 403

    # Zoya cannot view Om's access summary
    r = seeded_client.get("/users/om-agrawal/access", headers={"X-User-Id": "zoya-ansari"})
    assert r.status_code == 403

    # Rajesh (client user) cannot view Om's grants
    r = seeded_client.get("/users/om-agrawal/grants", headers={"X-User-Id": "rajesh-gupta"})
    assert r.status_code == 403

    # But Zoya CAN view her own access summary
    r = seeded_client.get("/users/zoya-ansari/access", headers={"X-User-Id": "zoya-ansari"})
    assert r.status_code == 200
    assert r.json()["user_id"] == "zoya-ansari"

    # And Rajesh CAN view his own access summary
    r = seeded_client.get("/users/rajesh-gupta/access", headers={"X-User-Id": "rajesh-gupta"})
    assert r.status_code == 200
    assert r.json()["user_id"] == "rajesh-gupta"

    # Rajesh (client user) sees only himself in /users directory (no staff leakage)
    r = seeded_client.get("/users", headers={"X-User-Id": "rajesh-gupta"})
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == "rajesh-gupta"


def test_unauthorized_decide_and_compare_blocked(seeded_client: TestClient):
    """Zoya and Rajesh cannot evaluate other users or run explain/compare."""
    # Zoya cannot dry-run decision for Om
    r = seeded_client.get(
        "/decide?user_id=om-agrawal&action=check&job_id=JOB-SHOWCASE-01",
        headers={"X-User-Id": "zoya-ansari"},
    )
    assert r.status_code == 403

    # Zoya cannot run explain/compare
    r = seeded_client.get(
        "/explain/compare?users=priya-nair,faisal-khan&action=check&job_id=JOB-SHOWCASE-05",
        headers={"X-User-Id": "zoya-ansari"},
    )
    assert r.status_code == 403

    # Rajesh (client user C01) cannot probe jobs of Client C02 (404 isolation)
    r = seeded_client.get(
        "/decide?user_id=rajesh-gupta&action=view&job_id=JOB-SHOWCASE-02",
        headers={"X-User-Id": "rajesh-gupta"},
    )
    assert r.status_code == 404


def test_unauthorized_who_could_blocked(seeded_client: TestClient):
    """Zoya and Rajesh cannot run audit who-could queries."""
    # Zoya on JOB-SHOWCASE-01 -> 404 Not Found (cannot view job)
    r = seeded_client.get(
        "/jobs/JOB-SHOWCASE-01/who-could?action=prepare",
        headers={"X-User-Id": "zoya-ansari"},
    )
    assert r.status_code in (403, 404)

    # Rajesh on JOB-SHOWCASE-01 (C01 shipment) -> 403 Forbidden (no audit.view)
    r = seeded_client.get(
        "/jobs/JOB-SHOWCASE-01/who-could?action=prepare",
        headers={"X-User-Id": "rajesh-gupta"},
    )
    assert r.status_code == 403


def test_authorized_super_admin_can_query_all(seeded_client: TestClient):
    """Om Agrawal (Super Admin holding access.manage and audit.view) can inspect all."""
    # View Rohit's grants
    r = seeded_client.get("/users/rohit-mehta/grants", headers={"X-User-Id": "om-agrawal"})
    assert r.status_code == 200

    # View Rohit's access summary
    r = seeded_client.get("/users/rohit-mehta/access", headers={"X-User-Id": "om-agrawal"})
    assert r.status_code == 200

    # Evaluate decision for Rohit
    r = seeded_client.get(
        "/decide?user_id=rohit-mehta&action=check&job_id=JOB-SHOWCASE-05",
        headers={"X-User-Id": "om-agrawal"},
    )
    assert r.status_code == 200
    assert r.json()["allowed"] is True

    # Run explain/compare
    r = seeded_client.get(
        "/explain/compare?users=priya-nair,faisal-khan&action=check&job_id=JOB-SHOWCASE-05",
        headers={"X-User-Id": "om-agrawal"},
    )
    assert r.status_code == 200

    # Run who-could
    r = seeded_client.get(
        "/jobs/JOB-HIST-DEMO-01/who-could?action=prepare&at=2026-10-03T14:00:00Z",
        headers={"X-User-Id": "om-agrawal"},
    )
    assert r.status_code == 200
