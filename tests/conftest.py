"""Pytest fixtures for Nagarkot Access Control Service test suite."""
import os
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, init_db, get_db
from app.clock import set_time, reset_time, get_now
from scripts.seed import seed as run_seed
from app.models import (
    User,
    Branch,
    Client,
    Role,
    RolePermission,
    Grant,
    Job,
    SoDRule,
    Approval,
    AuditLog,
)
from app.permissions import (
    JOB_VIEW,
    JOB_VIEW_INTERNAL,
    JOB_CREATE,
    JOB_UPDATE_UNFILED,
    JOB_PREPARE,
    JOB_CHECK,
    JOB_FILE,
    JOB_CANCEL,
    JOB_CANCEL_FILED,
    JOB_REOPEN,
    JOB_APPROVE_SENSITIVE,
    JOB_REASSIGN,
    JOB_OVERRIDE,
    ACCESS_MANAGE,
    ACCESS_MANAGE_PRIVILEGED,
    ROLES_MANAGE,
    AUDIT_VIEW,
)


@pytest.fixture(autouse=True)
def clean_clock():
    """Ensure clock is reset after each test."""
    reset_time()
    yield
    reset_time()


@pytest.fixture
def db_engine():
    """Create a temporary in-memory SQLite database with foreign keys and triggers."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine):
    """Provide a transactional database session for tests."""
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client(db_engine):
    """Provide a TestClient with app.db.get_db dependency overridden to use the test engine."""
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app, raise_server_exceptions=True)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_db(db):
    """Provide a test database session seeded with full standard seed data."""
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    set_time(now)
    run_seed(db, now=now)
    return db


@pytest.fixture
def seeded_client(seeded_db, client):
    """Provide a TestClient against the seeded test database."""
    return client


@pytest.fixture
def seed_basic_catalogue(db):
    """Seed standard branches, clients, core roles, and role permissions."""
    now = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    set_time(now)

    # Branches
    branches = [
        Branch(id="BR-MUM", name="Mumbai-Fort", code="MUM"),
        Branch(id="BR-NS", name="Nhava Sheva", code="NS"),
        Branch(id="BR-DEL", name="Delhi-ICD", code="DEL"),
        Branch(id="BR-MAA", name="Chennai", code="MAA"),
        Branch(id="BR-CCU", name="Kolkata", code="CCU"),
    ]
    db.add_all(branches)

    # Clients
    clients = [Client(id=f"C{i:02d}", name=f"Client {i:02d}") for i in range(1, 11)]
    db.add_all(clients)

    # Roles
    roles_def = {
        "viewer": ("Viewer", "staff", [JOB_VIEW]),
        "maker": ("Maker", "staff", [JOB_VIEW, JOB_VIEW_INTERNAL, JOB_PREPARE]),
        "checker": ("Checker", "staff", [JOB_VIEW, JOB_VIEW_INTERNAL, JOB_CHECK]),
        "filer": ("Filer", "staff", [JOB_VIEW, JOB_VIEW_INTERNAL, JOB_FILE]),
        "supervisor": ("Supervisor", "staff", [JOB_VIEW, JOB_VIEW_INTERNAL, JOB_CANCEL, JOB_REASSIGN]),
        "approver": ("Approver", "staff", [JOB_VIEW, JOB_VIEW_INTERNAL, JOB_CANCEL_FILED, JOB_REOPEN, JOB_APPROVE_SENSITIVE]),
        "access_admin": ("Access Admin", "staff", [ACCESS_MANAGE, AUDIT_VIEW, JOB_VIEW]),
        "ops_admin": ("Ops Admin", "staff", [JOB_VIEW, JOB_VIEW_INTERNAL, JOB_OVERRIDE, JOB_REASSIGN, AUDIT_VIEW]),
        "super_admin": ("Super Admin", "staff", [ACCESS_MANAGE, ACCESS_MANAGE_PRIVILEGED, ROLES_MANAGE, AUDIT_VIEW]),
        "client_viewer": ("Client Viewer", "client", [JOB_VIEW]),
        "parser": ("Parser", "system", [JOB_CREATE, JOB_UPDATE_UNFILED]),
    }

    catalogue_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    for r_id, (r_name, r_types, perms) in roles_def.items():
        role = Role(id=r_id, name=r_name, allowed_user_types=r_types, created_at=catalogue_start)
        db.add(role)
        for p in perms:
            rp = RolePermission(role_id=r_id, permission=p, added_at=catalogue_start)
            db.add(rp)

    # SoD Rules
    sod1 = SoDRule(
        id="sod_maker_checker",
        name="Maker-Checker Conflict",
        action="check",
        conflicting_field="prepared_by",
        description="A user who prepared a job cannot check it in the same cycle",
    )
    sod2 = SoDRule(
        id="sod_self_approval",
        name="Self Approval Conflict",
        action="approve_sensitive",
        conflicting_field="requested_by",
        description="A user who requested a sensitive action cannot approve it",
    )
    db.add_all([sod1, sod2])

    db.commit()
    return {
        "now": now,
        "branches": branches,
        "clients": clients,
    }
