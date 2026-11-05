"""High-performance scale data generator for Nagarkot Access Control Service.

Generates 500 users with realistic grant allocations and 200,000 shipment jobs
using chunked bulk insertions into SQLite WAL database.
"""
import argparse
import random
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db
from sqlalchemy import create_engine
from app.models import (
    Branch,
    Client,
    Role,
    RolePermission,
    User,
    Grant,
    Job,
    SoDRule,
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


def generate_scale(num_users: int = 500, num_jobs: int = 200000, db_url: str = "sqlite:///./scale.db"):
    print(f"--- Generating Scale Dataset: {num_users} Users & {num_jobs} Jobs on {db_url} ---")
    start_time = time.perf_counter()

    if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:///:memory:"):
        db_file = Path(db_url.replace("sqlite:///", ""))
        for f in [db_file, Path(str(db_file) + "-wal"), Path(str(db_file) + "-shm")]:
            if f.exists():
                try:
                    f.unlink()
                except Exception as e:
                    print(f"Note removing {f}: {e}")

    scale_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
        echo=False,
    )
    init_db(target_engine=scale_engine)

    conn = scale_engine.raw_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA cache_size = -64000;")  # 64MB cache
    cursor.execute("PRAGMA journal_mode = WAL;")

    random.seed(42)
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    now_iso = now.isoformat()
    t_cat = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat()

    # 1. Branches & Clients
    branches = [
        ("BR-MUM", "Mumbai-Fort", "MUM"),
        ("BR-NS", "Nhava Sheva", "NS"),
        ("BR-DEL", "Delhi-ICD", "DEL"),
        ("BR-MAA", "Chennai", "MAA"),
        ("BR-CCU", "Kolkata", "CCU"),
    ]
    cursor.executemany("INSERT INTO branches (id, name, code) VALUES (?, ?, ?);", branches)

    clients = [(f"C{i+1:02d}", f"Client {i+1:02d}") for i in range(10)]
    cursor.executemany("INSERT INTO clients (id, name) VALUES (?, ?);", clients)

    # 2. Roles & Permissions
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

    role_rows = []
    rp_rows = []
    for r_id, (r_name, r_types, perms) in roles_def.items():
        role_rows.append((r_id, r_name, r_types, t_cat))
        for p in perms:
            rp_rows.append((r_id, p, t_cat, None))

    cursor.executemany("INSERT INTO roles (id, name, allowed_user_types, created_at) VALUES (?, ?, ?, ?);", role_rows)
    cursor.executemany("INSERT INTO role_permissions (role_id, permission, added_at, removed_at) VALUES (?, ?, ?, ?);", rp_rows)

    # SoD rules
    cursor.execute("""
        INSERT INTO sod_rules (id, name, action, conflicting_field, description) VALUES
        ('sod_maker_checker', 'Maker-Checker Conflict', 'check', 'prepared_by', 'Maker cannot check in same cycle'),
        ('sod_self_approval', 'Self Approval Conflict', 'approve_sensitive', 'requested_by', 'Requester cannot approve');
    """)

    # 3. Seed Users
    # Preserve 20 Key Personas
    user_rows = [
        ("asha-rao", "Asha Rao", "staff", "active", None, now_iso),
        ("rohit-mehta", "Rohit Mehta", "staff", "active", None, now_iso),
        ("neha-kulkarni", "Neha Kulkarni", "staff", "active", None, now_iso),
        ("imran-shaikh", "Imran Shaikh", "staff", "absent", None, now_iso),
        ("pooja-sharma", "Pooja Sharma", "staff", "active", None, now_iso),
        ("priya-nair", "Priya Nair", "staff", "active", None, now_iso),
        ("karan-shah", "Karan Shah", "staff", "active", None, now_iso),
        ("anita-dsouza", "Anita D'Souza", "staff", "active", None, now_iso),
        ("tarun-das", "Tarun Das", "staff", "active", None, now_iso),
        ("vikram-joshi", "Vikram Joshi", "staff", "active", None, now_iso),
        ("sunita-patil", "Sunita Patil", "staff", "active", None, now_iso),
        ("deepak-verma", "Deepak Verma", "staff", "active", None, now_iso),
        ("meera-iyer", "Meera Iyer", "staff", "active", None, now_iso),
        ("om-agrawal", "Om Agrawal", "staff", "active", None, now_iso),
        ("faisal-khan", "Faisal Khan", "staff", "active", None, now_iso),
        ("lakshmi-iyer", "Lakshmi Iyer", "staff", "active", None, now_iso),
        ("arjun-reddy", "Arjun Reddy", "staff", "active", None, now_iso),
        ("rajesh-gupta", "Rajesh Gupta", "client", "active", "C01", now_iso),
        ("sneha-kapoor", "Sneha Kapoor", "client", "active", "C06", now_iso),
        ("overnight-parser", "Overnight Parser", "system", "active", None, now_iso),
        ("zoya-ansari", "Zoya Ansari", "staff", "active", None, now_iso),
    ]

    # Additional users up to num_users
    if len(user_rows) > num_users:
        user_rows = user_rows[:num_users]
    else:
        for u_idx in range(len(user_rows) + 1, num_users + 1):
            if u_idx <= 420:
                user_rows.append((f"USR-STAFF-{u_idx:03d}", f"Staff Member {u_idx}", "staff", "active", None, now_iso))
            elif u_idx <= 495:
                cid = f"C{(u_idx % 10) + 1:02d}"
                user_rows.append((f"USR-CLIENT-{u_idx:03d}", f"Client Contact {u_idx}", "client", "active", cid, now_iso))
            else:
                user_rows.append((f"USR-SYS-{u_idx:03d}", f"System Agent {u_idx}", "system", "active", None, now_iso))

    cursor.executemany("INSERT INTO users (id, name, type, status, client_id, created_at) VALUES (?, ?, ?, ?, ?, ?);", user_rows)

    valid_user_ids = {u[0] for u in user_rows}

    # 4. Seed Grants
    grant_rows = [
        # Asha Rao
        ("grt-asha-maker", "asha-rao", "maker", None, None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "National Maker", None, "b-asha"),
        ("grt-asha-chk-c03", "asha-rao", "checker", "C03", None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Checker C03", None, "b-asha"),
        ("grt-asha-chk-c05", "asha-rao", "checker", "C05", None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Checker C05", None, "b-asha"),
        ("grt-asha-chk-c07", "asha-rao", "checker", "C07", None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Checker C07", None, "b-asha"),
        # Rohit Mehta
        ("grt-rohit-chk", "rohit-mehta", "checker", "C01", "BR-MUM", "IMPORT", None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Checker C01 Mum Imp", None, "b-rohit"),
        # Neha Kulkarni
        ("grt-neha-mum", "neha-kulkarni", "filer", None, "BR-MUM", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Filer MUM", None, "b-neha"),
        ("grt-neha-ns", "neha-kulkarni", "filer", None, "BR-NS", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Filer NS", None, "b-neha"),
        # Imran Shaikh
        ("grt-imran-maker", "imran-shaikh", "maker", None, "BR-DEL", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Maker DEL", None, "b-imran"),
        # Pooja Sharma
        ("grt-pooja-chk", "pooja-sharma", "checker", None, None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "National Checker", None, "b-pooja"),
        ("grt-pooja-cover", "pooja-sharma", "maker", None, "BR-DEL", None, None, "allow", (now - timedelta(days=2)).isoformat(), (now + timedelta(days=5)).isoformat(), "om-agrawal", now_iso, None, None, "Cover for Imran", "imran-shaikh", "b-pooja"),
        # Priya Nair
        ("grt-priya-chk", "priya-nair", "checker", None, None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Checker All", None, "b-priya"),
        # Karan Shah
        ("grt-karan-mkr", "karan-shah", "maker", "C02", "BR-MAA", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Maker C02 MAA", None, "b-karan"),
        ("grt-karan-chk", "karan-shah", "checker", "C02", "BR-MAA", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Checker C02 MAA", None, "b-karan"),
        # Anita D'Souza
        ("grt-anita-mkr", "anita-dsouza", "maker", None, None, "EXPORT", "AIR", "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Export Air Maker", None, "b-anita"),
        # Tarun Das
        ("grt-tarun-mkr", "tarun-das", "maker", None, "BR-CCU", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Kolkata Maker", None, "b-tarun"),
        ("grt-tarun-deny", "tarun-das", "maker", "C04", None, None, None, "deny", now_iso, None, "om-agrawal", now_iso, None, None, "Deny C04", None, "b-tarun"),
        # Vikram Joshi
        ("grt-vikram-sup", "vikram-joshi", "supervisor", None, "BR-MUM", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "MUM Supervisor", None, "b-vikram"),
        # Sunita Patil
        ("grt-sunita-app", "sunita-patil", "approver", None, None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Approver All", None, "b-sunita"),
        # Deepak Verma
        ("grt-deepak-mum", "deepak-verma", "access_admin", None, "BR-MUM", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Access Admin MUM", None, "b-deepak"),
        ("grt-deepak-ns", "deepak-verma", "access_admin", None, "BR-NS", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Access Admin NS", None, "b-deepak"),
        # Meera Iyer
        ("grt-meera-ops", "meera-iyer", "ops_admin", None, None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Ops Admin", None, "b-meera"),
        # Om Agrawal
        ("grt-om-sa", "om-agrawal", "super_admin", None, None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Super Admin", None, "b-om"),
        # Faisal Khan
        ("grt-faisal-view", "faisal-khan", "viewer", None, None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Viewer All", None, "b-faisal"),
        # Lakshmi Iyer
        ("grt-lakshmi-maa", "lakshmi-iyer", "filer", None, "BR-MAA", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Filer MAA", None, "b-lakshmi"),
        ("grt-lakshmi-ccu", "lakshmi-iyer", "filer", None, "BR-CCU", None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Filer CCU", None, "b-lakshmi"),
        # Rajesh Gupta
        ("grt-rajesh-cl", "rajesh-gupta", "client_viewer", "C01", None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Client Viewer C01", None, "b-rajesh"),
        # Sneha Kapoor
        ("grt-sneha-cl", "sneha-kapoor", "client_viewer", "C06", None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "Client Viewer C06", None, "b-sneha"),
        # overnight-parser
        ("grt-parser-sys", "overnight-parser", "parser", None, None, None, None, "allow", now_iso, None, "om-agrawal", now_iso, None, None, "System Parser", None, "b-parser"),
    ]

    # Additional staff grants
    staff_roles = ["maker", "checker", "filer", "supervisor", "viewer"]
    b_ids = [b[0] for b in branches]
    for u_idx in range(22, 421):
        uid = f"USR-STAFF-{u_idx:03d}"
        role_choice = random.choice(staff_roles)
        branch_choice = random.choice(b_ids) if random.random() < 0.7 else None
        client_choice = f"C{random.randint(1, 10):02d}" if random.random() < 0.3 else None
        grant_rows.append((
            f"grt-sc-{u_idx}", uid, role_choice, client_choice, branch_choice, None, None,
            "allow", now_iso, None, "om-agrawal", now_iso, None, None, f"Scale grant {u_idx}", None, f"b-scale-{u_idx}"
        ))

    # Client viewer grants
    for u_idx in range(421, 496):
        uid = f"USR-CLIENT-{u_idx:03d}"
        cid = f"C{(u_idx % 10) + 1:02d}"
        grant_rows.append((
            f"grt-cl-{u_idx}", uid, "client_viewer", cid, None, None, None,
            "allow", now_iso, None, "om-agrawal", now_iso, None, None, f"Client grant {u_idx}", None, f"b-cl-{u_idx}"
        ))

    grant_rows = [g for g in grant_rows if g[1] in valid_user_ids]
    cursor.executemany("""
        INSERT INTO grants (
            id, user_id, role_id, client_id, branch_id, direction, mode, effect,
            valid_from, valid_to, granted_by, created_at, revoked_at, revoked_by,
            reason, cover_for_user_id, batch_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, grant_rows)
    conn.commit()

    print(f"Inserted {len(user_rows)} users and {len(grant_rows)} grants.")

    # 5. Seed Jobs in fast chunks
    print(f"Generating and bulk inserting {num_jobs} jobs in chunks of 10,000...")

    # Static showcase jobs first
    showcase_jobs = [
        ("JOB-SHOWCASE-01", "NF-SHOWCASE-FILED", "C01", "BR-MUM", "IMPORT", "AIR", "FILED", None, "asha-rao", "rohit-mehta", "neha-kulkarni", 1, "Showcase Filed", "overnight-parser", now_iso, now_iso),
        ("JOB-SHOWCASE-02", "NF-SHOWCASE-PREPARED-SOD", "C03", "BR-MUM", "IMPORT", "AIR", "PREPARED", None, "asha-rao", None, None, 1, "Showcase SoD Conflict", "overnight-parser", now_iso, now_iso),
        ("JOB-SHOWCASE-03", "NF-SHOWCASE-STUCK", "C05", "BR-DEL", "IMPORT", "FCL", "PREPARED", "imran-shaikh", "imran-shaikh", None, None, 1, "Showcase Stuck Ops", "overnight-parser", now_iso, now_iso),
        ("JOB-SHOWCASE-04", "NF-SHOWCASE-ARJUN-REVOKED", "C08", "BR-MUM", "IMPORT", "AIR", "PREPARED", None, "asha-rao", None, None, 1, "Showcase Arjun Revoked", "overnight-parser", now_iso, now_iso),
        ("JOB-SHOWCASE-05", "NF-SHOWCASE-ROHIT-CHECK", "C01", "BR-MUM", "IMPORT", "AIR", "PREPARED", None, "asha-rao", None, None, 1, "Showcase Rohit Check", "overnight-parser", now_iso, now_iso),
        ("JOB-SHOWCASE-06", "NF-SHOWCASE-ROHIT-EXPORT", "C01", "BR-MUM", "EXPORT", "AIR", "PREPARED", None, "asha-rao", None, None, 1, "Showcase Rohit Export", "overnight-parser", now_iso, now_iso),
        ("JOB-SHOWCASE-07", "NF-SHOWCASE-ROHIT-OTHER-BRANCH", "C01", "BR-NS", "IMPORT", "AIR", "PREPARED", None, "asha-rao", None, None, 1, "Showcase Rohit Branch", "overnight-parser", now_iso, now_iso),
        ("JOB-SHOWCASE-08", "NF-SHOWCASE-DELHI-CONFIRMED", "C05", "BR-DEL", "IMPORT", "FCL", "CONFIRMED", None, None, None, None, 1, "Showcase Delhi Confirmed", "overnight-parser", now_iso, now_iso),
    ]
    if len(showcase_jobs) > num_jobs:
        showcase_jobs = showcase_jobs[:num_jobs]

    cursor.executemany("""
        INSERT INTO jobs (
            id, ref, client_id, branch_id, direction, mode, stage,
            assigned_to, prepared_by, checked_by, filed_by, cycle,
            internal_notes, created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, showcase_jobs)

    stages = ["CONFIRMED", "PREPARED", "CHECKED", "FILED", "CANCELLED", "REOPENED"]
    directions = ["IMPORT", "EXPORT"]
    modes = ["AIR", "FCL", "LCL"]
    branch_keys = [b[0] for b in branches]
    client_keys = [c[0] for c in clients]

    chunk_size = 10000
    total_chunks = (num_jobs - len(showcase_jobs) + chunk_size - 1) // chunk_size
    job_counter = len(showcase_jobs) + 1

    for chunk_idx in range(total_chunks):
        chunk_jobs = []
        rows_to_make = min(chunk_size, num_jobs - job_counter + 1)
        for _ in range(rows_to_make):
            j_id = f"JOB-SC-{job_counter:07d}"
            c_id = random.choice(client_keys)
            b_id = random.choice(branch_keys)
            dir_v = random.choice(directions)
            mode_v = random.choice(modes)
            stage_v = random.choice(stages)
            ref_v = f"NF-{dir_v[:3]}-{mode_v[:3]}-{job_counter:07d}"

            # Timestamps
            days_offset = random.uniform(0.1, 60.0)
            created_dt = now - timedelta(days=days_offset)
            updated_dt = created_dt + timedelta(hours=random.uniform(0.5, 8.0))
            c_iso = created_dt.isoformat()
            u_iso = updated_dt.isoformat()

            p_by = "asha-rao" if stage_v in ("PREPARED", "CHECKED", "FILED") else None
            c_by = "priya-nair" if stage_v in ("CHECKED", "FILED") else None
            f_by = "neha-kulkarni" if stage_v == "FILED" else None
            assigned_v = None
            if stage_v in ("CONFIRMED", "PREPARED", "CHECKED", "REOPENED") and random.random() < 0.3:
                assigned_v = random.choice(["asha-rao", "priya-nair", "pooja-sharma", "karan-shah"])

            chunk_jobs.append((
                j_id, ref_v, c_id, b_id, dir_v, mode_v, stage_v,
                assigned_v, p_by, c_by, f_by, 1,
                f"Scale shipment record {job_counter}", "overnight-parser", c_iso, u_iso
            ))
            job_counter += 1

        cursor.executemany("""
            INSERT INTO jobs (
                id, ref, client_id, branch_id, direction, mode, stage,
                assigned_to, prepared_by, checked_by, filed_by, cycle,
                internal_notes, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, chunk_jobs)
        conn.commit()

        pct = (job_counter / num_jobs) * 100
        print(f"  -> Bulk progress: {job_counter - 1:,} / {num_jobs:,} jobs ({pct:.1f}%)")

    cursor.close()
    conn.close()
    scale_engine.dispose()

    elapsed = time.perf_counter() - start_time
    print(f"\nScale generation completed in {elapsed:.2f} seconds!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate scale data for Nagarkot Access Control")
    parser.add_argument("--users", type=int, default=500, help="Number of users to generate (default 500)")
    parser.add_argument("--jobs", type=int, default=200000, help="Number of jobs to generate (default 200,000)")
    parser.add_argument("--db", type=str, default="sqlite:///./scale.db", help="Target database URL (default sqlite:///./scale.db)")
    args = parser.parse_args()

    generate_scale(num_users=args.users, num_jobs=args.jobs, db_url=args.db)
