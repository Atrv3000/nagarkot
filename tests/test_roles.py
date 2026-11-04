"""Tests for dynamic data-driven role creation and permission updates."""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException

from app.models import User, Grant, Role, RolePermission
from app.routers.roles import create_role, update_role_permissions
from app.schemas import RoleCreate, RolePermissionsUpdate
from app.permissions import JOB_VIEW, JOB_CHECK, ROLES_MANAGE, ACCESS_MANAGE_PRIVILEGED


def test_create_new_role_takes_effect_without_deploy(db, seed_basic_catalogue):
    """New role created dynamically in database is immediately assignable and functional."""
    now = seed_basic_catalogue["now"]
    super_admin = User(id="om-agrawal", name="Om", type="staff", status="active", created_at=now)
    db.add(super_admin)
    g_om = Grant(
        id="g-om", user_id="om-agrawal", role_id="super_admin", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="bootstrap", created_at=now, reason="Super Admin", batch_id="b0"
    )
    db.add(g_om)
    db.commit()

    # Dynamically create new role "night_auditor" with [job.view, audit.view]
    new_role_data = RoleCreate(
        id="night_auditor",
        name="Night Auditor",
        allowed_user_types=["staff"],
        permissions=["job.view", "audit.view"],
    )
    res = create_role(new_role_data, caller=super_admin, db=db)
    assert res.id == "night_auditor"

    # Verify role exists in DB
    role_in_db = db.query(Role).filter(Role.id == "night_auditor").first()
    assert role_in_db is not None
    rps = db.query(RolePermission).filter(RolePermission.role_id == "night_auditor").all()
    assert {rp.permission for rp in rps} == {"job.view", "audit.view"}


def test_cannot_edit_own_role(db, seed_basic_catalogue):
    """A user cannot edit the permissions of a role they currently hold an active grant for."""
    now = seed_basic_catalogue["now"]
    user = User(id="om-agrawal", name="Om", type="staff", status="active", created_at=now)
    db.add(user)
    g_om = Grant(
        id="g-om", user_id="om-agrawal", role_id="super_admin", effect="allow",
        valid_from=now - timedelta(days=1), granted_by="bootstrap", created_at=now, reason="Super Admin", batch_id="b0"
    )
    db.add(g_om)
    db.commit()

    # Om holds super_admin, attempts to edit super_admin role permissions
    update_data = RolePermissionsUpdate(
        permissions=["roles.manage"],
        reason="Trying to modify own role",
    )
    with pytest.raises(HTTPException) as exc_info:
        update_role_permissions(id="super_admin", body=update_data, caller=user, db=db)

    assert exc_info.value.status_code == 403
    assert "cannot edit role 'super_admin' because you currently hold" in exc_info.value.detail
