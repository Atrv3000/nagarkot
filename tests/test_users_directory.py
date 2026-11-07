"""Tests for public GET /users directory endpoint."""
import pytest
from starlette.testclient import TestClient


def test_users_directory_returns_all_personas(seeded_client: TestClient):
    """GET /users returns all 21 seeded personas with safe metadata and role labels."""
    resp = seeded_client.get("/users")
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
