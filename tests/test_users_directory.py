"""Tests for authenticated GET /users directory endpoint."""
import pytest
from starlette.testclient import TestClient


def test_users_directory_auth_required(seeded_client: TestClient):
    """GET /users requires X-User-Id header and rejects unauthenticated or unknown callers."""
    # Missing header -> 401
    resp_no_header = seeded_client.get("/users")
    assert resp_no_header.status_code == 401

    # Unknown user -> 401
    resp_unknown = seeded_client.get("/users", headers={"X-User-Id": "unknown-user-id"})
    assert resp_unknown.status_code == 401


def test_users_directory_staff_sees_all_personas(seeded_client: TestClient):
    """Staff caller (Asha Rao) receives all 21 seeded personas with safe metadata and role labels."""
    resp = seeded_client.get("/users", headers={"X-User-Id": "asha-rao"})
    assert resp.status_code == 200
    data = resp.json()

    assert len(data) >= 21
    users_by_id = {u["id"]: u for u in data}

    # Verify key personas and role labels
    assert "asha-rao" in users_by_id
    assert users_by_id["asha-rao"]["name"] == "Asha Rao"
    assert users_by_id["asha-rao"]["type"] == "staff"
    assert users_by_id["asha-rao"]["status"] == "active"
    assert "Maker" in users_by_id["asha-rao"]["role_label"]
    assert "Checker" in users_by_id["asha-rao"]["role_label"]

    assert "rohit-mehta" in users_by_id
    assert users_by_id["rohit-mehta"]["role_label"] == "Checker"

    assert "imran-shaikh" in users_by_id
    assert users_by_id["imran-shaikh"]["status"] == "absent"
    assert users_by_id["imran-shaikh"]["role_label"] == "Maker"

    assert "pooja-sharma" in users_by_id
    assert "Checker" in users_by_id["pooja-sharma"]["role_label"]
    assert "Cover" in users_by_id["pooja-sharma"]["role_label"]

    assert "om-agrawal" in users_by_id
    assert users_by_id["om-agrawal"]["role_label"] == "Super Admin"

    assert "rajesh-gupta" in users_by_id
    assert users_by_id["rajesh-gupta"]["type"] == "client"
    assert users_by_id["rajesh-gupta"]["client_id"] == "C01"
    assert users_by_id["rajesh-gupta"]["role_label"] == "Client Viewer"

    assert "zoya-ansari" in users_by_id
    assert users_by_id["zoya-ansari"]["role_label"] == "None"

    assert "arjun-reddy" in users_by_id
    assert "Revoked" in users_by_id["arjun-reddy"]["role_label"]


def test_users_directory_client_sees_only_themselves(seeded_client: TestClient):
    """Client caller (Rajesh Gupta) only sees their own record, maintaining staff privacy."""
    resp = seeded_client.get("/users", headers={"X-User-Id": "rajesh-gupta"})
    assert resp.status_code == 200
    data = resp.json()

    assert len(data) == 1
    assert data[0]["id"] == "rajesh-gupta"
    assert data[0]["type"] == "client"
    assert data[0]["client_id"] == "C01"
