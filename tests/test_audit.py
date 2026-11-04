"""Tests verifying audit immutability triggers and audit logging coverage."""
import pytest
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DatabaseError

from app.models import AuditLog
from app.audit import log_audit_event


def test_audit_log_triggers_reject_update(db, seed_basic_catalogue):
    """Database triggers prohibit UPDATE statements on audit_log table."""
    now = seed_basic_catalogue["now"]
    entry = log_audit_event(
        db=db,
        actor_id="test-actor",
        actor_type="staff",
        event_type="JOB_ACTION",
        action="prepare",
        decision="EXECUTE",
        job_id="JOB-123",
        at=now,
    )
    db.commit()

    # Attempt direct SQL UPDATE on audit_log
    with pytest.raises(DatabaseError) as exc_info:
        db.execute(
            text("UPDATE audit_log SET actor_id = 'hacker' WHERE id = :id"),
            {"id": entry.id},
        )
        db.commit()

    assert "Audit log is append-only: UPDATE prohibited" in str(exc_info.value)
    db.rollback()


def test_audit_log_triggers_reject_delete(db, seed_basic_catalogue):
    """Database triggers prohibit DELETE statements on audit_log table."""
    now = seed_basic_catalogue["now"]
    entry = log_audit_event(
        db=db,
        actor_id="test-actor",
        actor_type="staff",
        event_type="JOB_ACTION",
        action="file",
        decision="EXECUTE",
        job_id="JOB-456",
        at=now,
    )
    db.commit()

    # Attempt direct SQL DELETE on audit_log
    with pytest.raises(DatabaseError) as exc_info:
        db.execute(
            text("DELETE FROM audit_log WHERE id = :id"),
            {"id": entry.id},
        )
        db.commit()

    assert "Audit log is append-only: DELETE prohibited" in str(exc_info.value)
    db.rollback()
