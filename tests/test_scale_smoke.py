"""Fast smoke test for scale generator and equivalence under generated data."""
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import User, Job
from app.decision import decide
from app.scope import compile_my_queue_predicate
from scripts.generate_scale import generate_scale


def test_scale_generation_smoke(tmp_path):
    """Generate 20 users and 500 jobs into a temp database and verify queue-vs-decide equivalence."""
    db_file = tmp_path / "scale_smoke.db"
    db_url = f"sqlite:///{db_file}"
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Generate small scale dataset
    generate_scale(num_users=20, num_jobs=500, db_url=db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        user_count = db.query(User).count()
        job_count = db.query(Job).count()

        assert user_count == 20, f"Expected 20 users, got {user_count}"
        assert job_count == 500, f"Expected 500 jobs, got {job_count}"

        # 2. Sample 10 users and verify queue-vs-decide equivalence
        users = db.query(User).limit(10).all()
        jobs = db.query(Job).all()
        absent_user_ids = {u.id for u in db.query(User).filter(User.status == "absent").all()}

        for user in users:
            expected_ids = set()
            if user.status == "active":
                for job in jobs:
                    assignee_ok = (
                        job.assigned_to is None
                        or job.assigned_to == user.id
                        or job.assigned_to in absent_user_ids
                    )
                    if not assignee_ok:
                        continue

                    next_action = None
                    if job.stage in ("CONFIRMED", "REOPENED"):
                        next_action = "prepare"
                    elif job.stage == "PREPARED":
                        next_action = "check"
                    elif job.stage == "CHECKED":
                        next_action = "file"

                    if not next_action:
                        continue

                    decision = decide(db, user_id=user.id, action=next_action, job=job, at=now)
                    if decision.allowed:
                        expected_ids.add(job.id)

            predicate = compile_my_queue_predicate(db, user, now)
            actual_jobs = db.query(Job).filter(predicate).all()
            actual_ids = {j.id for j in actual_jobs}

            assert actual_ids == expected_ids, (
                f"Smoke equivalence mismatch for user '{user.id}': "
                f"SQL={len(actual_ids)} vs Python={len(expected_ids)}"
            )

    finally:
        db.close()
        engine.dispose()
