"""Unit tests for the SQL scope compiler and keyset pagination."""
from datetime import datetime, timezone, timedelta
import pytest

from app.models import User, Job, Grant
from app.permissions import JOB_VIEW, JOB_PREPARE, JOB_CHECK
from app.scope import (
    compile_permission_scope,
    compile_jobs_view_predicate,
    compile_my_queue_predicate,
    paginate_jobs_query,
    format_cursor,
    parse_cursor,
)


def test_scope_view_for_client_user(db, seed_basic_catalogue):
    """Client user SQL predicate limits strictly to their own client ID."""
    now = seed_basic_catalogue["now"]
    client_user = User(
        id="client-rajesh",
        name="Rajesh Gupta",
        type="client",
        status="active",
        client_id="C01",
        created_at=now,
    )
    db.add(client_user)
    # Grant client viewer
    grt = Grant(
        id="grt-rajesh",
        user_id="client-rajesh",
        role_id="client_viewer",
        client_id="C01",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="admin",
        created_at=now - timedelta(days=1),
        reason="Client user for C01",
        batch_id="b1",
    )
    db.add(grt)

    # Add jobs for C01 and C02
    job1 = Job(
        id="JOB-1",
        ref="NF-IMP-AIR-001",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="CONFIRMED",
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    job2 = Job(
        id="JOB-2",
        ref="NF-IMP-AIR-002",
        client_id="C02",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="CONFIRMED",
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    db.add_all([job1, job2])
    db.commit()

    predicate = compile_jobs_view_predicate(db, client_user, now)
    visible_jobs = db.query(Job).filter(predicate).all()

    assert len(visible_jobs) == 1
    assert visible_jobs[0].id == "JOB-1"
    assert visible_jobs[0].client_id == "C01"


def test_my_queue_predicate_stages_and_sod(db, seed_basic_catalogue):
    """My queue predicate correctly includes ready jobs and enforces SoD (maker!=checker)."""
    now = seed_basic_catalogue["now"]
    # User holds Maker and Checker roles
    user = User(id="karan-shah", name="Karan", type="staff", status="active", created_at=now)
    db.add(user)
    grt_maker = Grant(
        id="grt-karan-maker",
        user_id="karan-shah",
        role_id="maker",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="admin",
        created_at=now - timedelta(days=1),
        reason="Maker",
        batch_id="b1",
    )
    grt_checker = Grant(
        id="grt-karan-checker",
        user_id="karan-shah",
        role_id="checker",
        effect="allow",
        valid_from=now - timedelta(days=1),
        granted_by="admin",
        created_at=now - timedelta(days=1),
        reason="Checker",
        batch_id="b2",
    )
    db.add_all([grt_maker, grt_checker])

    # Job A: CONFIRMED stage -> needs prepare -> Karan can prepare
    job_a = Job(
        id="JOB-A",
        ref="NF-IMP-AIR-00A",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="CONFIRMED",
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    # Job B: PREPARED stage by someone else -> needs check -> Karan can check
    job_b = Job(
        id="JOB-B",
        ref="NF-IMP-AIR-00B",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="PREPARED",
        prepared_by="someone-else",
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    # Job C: PREPARED stage by Karan himself -> Maker/Checker conflict! -> Must NOT be in queue
    job_c = Job(
        id="JOB-C",
        ref="NF-IMP-AIR-00C",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="PREPARED",
        prepared_by="karan-shah",
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    db.add_all([job_a, job_b, job_c])
    db.commit()

    predicate = compile_my_queue_predicate(db, user, now)
    queue_jobs = db.query(Job).filter(predicate).all()
    queue_ids = {j.id for j in queue_jobs}

    assert "JOB-A" in queue_ids
    assert "JOB-B" in queue_ids
    assert "JOB-C" not in queue_ids  # Excluded due to SoD conflict


def test_keyset_pagination(db, seed_basic_catalogue):
    """Keyset pagination navigates pages deterministically without OFFSET."""
    now = seed_basic_catalogue["now"]
    for i in range(10):
        t = now + timedelta(minutes=i)
        j = Job(
            id=f"JOB-{i:03d}",
            ref=f"NF-PAGE-{i:03d}",
            client_id="C01",
            branch_id="BR-MUM",
            direction="IMPORT",
            mode="AIR",
            stage="CONFIRMED",
            created_by="admin",
            created_at=t,
            updated_at=t,
        )
        db.add(j)
    db.commit()

    query = db.query(Job)
    # First page of 3
    page1, cursor1 = paginate_jobs_query(query, limit=3)
    assert len(page1) == 3
    assert cursor1 is not None

    # Second page of 3
    page2, cursor2 = paginate_jobs_query(query, cursor=cursor1, limit=3)
    assert len(page2) == 3
    assert cursor2 is not None

    # Third page of 3
    page3, cursor3 = paginate_jobs_query(query, cursor=cursor2, limit=3)
    assert len(page3) == 3

    # All returned IDs are distinct
    p1_ids = [j.id for j in page1]
    p2_ids = [j.id for j in page2]
    p3_ids = [j.id for j in page3]
    all_seen = p1_ids + p2_ids + p3_ids
    assert len(all_seen) == len(set(all_seen))
