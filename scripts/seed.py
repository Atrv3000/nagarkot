"""Deterministic database seed script for Nagarkot Forwarders Pvt. Ltd.

Generates:
- 5 Branches (Mumbai-Fort, Nhava Sheva, Delhi-ICD, Chennai, Kolkata)
- 10 Fictional Clients (C01 to C10)
- 11 Core Roles with versioned permissions
- 20 Key Persona Users + Zoya Ansari (new joiner with zero grants)
- ~300 realistic jobs with chronological audit trails spanning the past 30 days
- Fixed showcase jobs for demo and verification
- Seed random with 42 for absolute determinism
"""
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import engine, init_db, SessionLocal
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


def seed():
    print("Initializing database tables and triggers...")
    init_db()

    db = SessionLocal()

    # Clear existing data
    db.query(Approval).delete()
    db.query(Job).delete()
    db.query(Grant).delete()
    db.query(RolePermission).delete()
    db.query(Role).delete()
    db.query(SoDRule).delete()
    db.query(User).delete()
    db.query(Client).delete()
    db.query(Branch).delete()
    # Note: audit_log table cannot be deleted via DELETE due to triggers!
    # If recreating from scratch, we can drop and recreate or let init_db handle
    db.commit()

    random.seed(42)
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    t_start = now - timedelta(days=35)
    t_catalogue = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    print("Seeding branches and clients...")
    branches = [
        Branch(id="BR-MUM", name="Mumbai-Fort", code="MUM"),
        Branch(id="BR-NS", name="Nhava Sheva", code="NS"),
        Branch(id="BR-DEL", name="Delhi-ICD", code="DEL"),
        Branch(id="BR-MAA", name="Chennai", code="MAA"),
        Branch(id="BR-CCU", name="Kolkata", code="CCU"),
    ]
    db.add_all(branches)

    client_names = [
        "Apex Global Traders",
        "Bharat Heavy Exports",
        "Coral Coastal Shipping",
        "Delta Chem Logistics",
        "Eastern Spice Enterprises",
        "Future Tech Electronics",
        "Garuda Auto Components",
        "Himalayan Agro Commodities",
        "Indus Textile Mills",
        "Jupiter Solar Systems",
    ]
    clients = [Client(id=f"C{i+1:02d}", name=client_names[i]) for i in range(10)]
    db.add_all(clients)

    print("Seeding roles and versioned permissions...")
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

    for r_id, (r_name, r_types, perms) in roles_def.items():
        role = Role(id=r_id, name=r_name, allowed_user_types=r_types, created_at=t_catalogue)
        db.add(role)
        for p in perms:
            db.add(RolePermission(role_id=r_id, permission=p, added_at=t_catalogue))

    # SoD rules
    db.add(SoDRule(
        id="sod_maker_checker",
        name="Maker-Checker Conflict",
        action="check",
        conflicting_field="prepared_by",
        description="A user who prepared a job cannot check it in the current cycle",
    ))
    db.add(SoDRule(
        id="sod_self_approval",
        name="Self Approval Conflict",
        action="approve_sensitive",
        conflicting_field="requested_by",
        description="A user who requested a sensitive action cannot approve it",
    ))

    print("Seeding the 20 key personas + Zoya Ansari...")
    users_data = [
        ("asha-rao", "Asha Rao", "staff", "active", None),
        ("rohit-mehta", "Rohit Mehta", "staff", "active", None),
        ("neha-kulkarni", "Neha Kulkarni", "staff", "active", None),
        ("imran-shaikh", "Imran Shaikh", "staff", "absent", None),
        ("pooja-sharma", "Pooja Sharma", "staff", "active", None),
        ("priya-nair", "Priya Nair", "staff", "active", None),
        ("karan-shah", "Karan Shah", "staff", "active", None),
        ("anita-dsouza", "Anita D'Souza", "staff", "active", None),
        ("tarun-das", "Tarun Das", "staff", "active", None),
        ("vikram-joshi", "Vikram Joshi", "staff", "active", None),
        ("sunita-patil", "Sunita Patil", "staff", "active", None),
        ("deepak-verma", "Deepak Verma", "staff", "active", None),
        ("meera-iyer", "Meera Iyer", "staff", "active", None),
        ("om-agrawal", "Om Agrawal", "staff", "active", None),
        ("faisal-khan", "Faisal Khan", "staff", "active", None),
        ("lakshmi-iyer", "Lakshmi Iyer", "staff", "active", None),
        ("arjun-reddy", "Arjun Reddy", "staff", "active", None),
        ("rajesh-gupta", "Rajesh Gupta", "client", "active", "C01"),
        ("sneha-kapoor", "Sneha Kapoor", "client", "active", "C06"),
        ("overnight-parser", "Overnight Parser", "system", "active", None),
        ("zoya-ansari", "Zoya Ansari", "staff", "active", None),
    ]

    for uid, name, utype, ustatus, cid in users_data:
        u = User(id=uid, name=name, type=utype, status=ustatus, client_id=cid, created_at=t_start)
        db.add(u)
    db.commit()

    # Record Imran status change audit event to preserve historical status replay
    imran_absent_time = now - timedelta(days=3)
    db.add(AuditLog(
        at=imran_absent_time,
        actor_id="om-agrawal",
        actor_type="staff",
        event_type="USER_STATUS_CHANGE",
        action="update_status",
        decision="EXECUTE",
        target_user_id="imran-shaikh",
        before_state={"status": "active"},
        after_state={"status": "absent", "reason": "Medical leave"},
    ))

    print("Seeding grants for personas...")
    grants = []
    # 1. Asha Rao: Maker for all; Checker for C03, C05, C07
    grants.append(Grant(
        id="grt-asha-maker", user_id="asha-rao", role_id="maker", effect="allow",
        valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Primary national maker", batch_id="b-asha"
    ))
    for cid in ["C03", "C05", "C07"]:
        grants.append(Grant(
            id=f"grt-asha-chk-{cid}", user_id="asha-rao", role_id="checker", client_id=cid, effect="allow",
            valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
            reason=f"Designated checker for client {cid}", batch_id="b-asha"
        ))

    # 2. Rohit Mehta: Checker for C01, Mumbai-Fort, IMPORT only, all modes
    grants.append(Grant(
        id="grt-rohit-chk", user_id="rohit-mehta", role_id="checker", client_id="C01", branch_id="BR-MUM",
        direction="IMPORT", effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Mumbai Fort import checker for C01", batch_id="b-rohit"
    ))

    # 3. Neha Kulkarni: Filer for Mumbai-Fort and Nhava Sheva, all clients
    for bid in ["BR-MUM", "BR-NS"]:
        grants.append(Grant(
            id=f"grt-neha-filer-{bid}", user_id="neha-kulkarni", role_id="filer", branch_id=bid,
            effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
            reason=f"Customs filer at {bid}", batch_id="b-neha"
        ))

    # 4. Imran Shaikh: Maker for Delhi-ICD (absent)
    grants.append(Grant(
        id="grt-imran-maker", user_id="imran-shaikh", role_id="maker", branch_id="BR-DEL",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Delhi ICD maker", batch_id="b-imran"
    ))

    # 5. Pooja Sharma: Checker everywhere + 7-day cover grant as Maker for Delhi-ICD (cover_for Imran)
    grants.append(Grant(
        id="grt-pooja-chk-all", user_id="pooja-sharma", role_id="checker", effect="allow",
        valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="National checker", batch_id="b-pooja"
    ))
    grants.append(Grant(
        id="grt-pooja-cover-imran", user_id="pooja-sharma", role_id="maker", branch_id="BR-DEL",
        effect="allow", valid_from=now - timedelta(days=2), valid_to=now + timedelta(days=5),
        granted_by="om-agrawal", created_at=now - timedelta(days=2),
        reason="7-day absence cover for Imran Shaikh", cover_for_user_id="imran-shaikh", batch_id="b-pooja-cover"
    ))

    # 6. Priya Nair: Checker for all clients and branches
    grants.append(Grant(
        id="grt-priya-chk-all", user_id="priya-nair", role_id="checker", effect="allow",
        valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Senior checker across all operations", batch_id="b-priya"
    ))

    # 7. Karan Shah: Maker AND Checker for client C02 at Chennai
    grants.append(Grant(
        id="grt-karan-maker-c02", user_id="karan-shah", role_id="maker", client_id="C02", branch_id="BR-MAA",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Chennai maker for C02", batch_id="b-karan"
    ))
    grants.append(Grant(
        id="grt-karan-chk-c02", user_id="karan-shah", role_id="checker", client_id="C02", branch_id="BR-MAA",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Chennai checker for C02", batch_id="b-karan"
    ))

    # 8. Anita D'Souza: Maker for EXPORTS, AIR mode only
    grants.append(Grant(
        id="grt-anita-maker-exp-air", user_id="anita-dsouza", role_id="maker", direction="EXPORT", mode="AIR",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Air export maker", batch_id="b-anita"
    ))

    # 9. Tarun Das: Maker at Kolkata with a DENY grant for client C04
    grants.append(Grant(
        id="grt-tarun-maker-ccu", user_id="tarun-das", role_id="maker", branch_id="BR-CCU",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Kolkata maker", batch_id="b-tarun"
    ))
    grants.append(Grant(
        id="grt-tarun-deny-c04", user_id="tarun-das", role_id="maker", client_id="C04",
        effect="deny", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Recusal: conflict of interest on client C04", batch_id="b-tarun"
    ))

    # 10. Vikram Joshi: Supervisor, Mumbai-Fort
    grants.append(Grant(
        id="grt-vikram-sup-mum", user_id="vikram-joshi", role_id="supervisor", branch_id="BR-MUM",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Mumbai branch operations supervisor", batch_id="b-vikram"
    ))

    # 11. Sunita Patil: Approver, all scope
    grants.append(Grant(
        id="grt-sunita-approver", user_id="sunita-patil", role_id="approver",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Head of customs compliance & sensitive approvals", batch_id="b-sunita"
    ))

    # 12. Deepak Verma: Access Admin (scope: all clients, branches Mumbai-Fort and Nhava Sheva only)
    for bid in ["BR-MUM", "BR-NS"]:
        grants.append(Grant(
            id=f"grt-deepak-access-{bid}", user_id="deepak-verma", role_id="access_admin", branch_id=bid,
            effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
            reason=f"Access administrator for {bid}", batch_id="b-deepak"
        ))

    # 13. Meera Iyer: Ops Admin
    grants.append(Grant(
        id="grt-meera-ops-admin", user_id="meera-iyer", role_id="ops_admin",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Central operations administrator", batch_id="b-meera"
    ))

    # 14. Om Agrawal: Super Admin (bootstrap)
    grants.append(Grant(
        id="grt-om-super-admin", user_id="om-agrawal", role_id="super_admin",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Founding super administrator", batch_id="b-om"
    ))

    # 15. Faisal Khan: Viewer, all scope
    grants.append(Grant(
        id="grt-faisal-viewer", user_id="faisal-khan", role_id="viewer",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Read-only operations viewer", batch_id="b-faisal"
    ))

    # 16. Lakshmi Iyer: Filer for Chennai and Kolkata
    for bid in ["BR-MAA", "BR-CCU"]:
        grants.append(Grant(
            id=f"grt-lakshmi-filer-{bid}", user_id="lakshmi-iyer", role_id="filer", branch_id=bid,
            effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
            reason=f"Customs filer for {bid}", batch_id="b-lakshmi"
        ))

    # 17. Arjun Reddy: Checker for C08 was revoked yesterday while he was assigned jobs
    grants.append(Grant(
        id="grt-arjun-revoked", user_id="arjun-reddy", role_id="checker", client_id="C08",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        revoked_at=now - timedelta(days=1), revoked_by="om-agrawal",
        reason="Revoked during territory realignment", batch_id="b-arjun"
    ))

    # 18. Rajesh Gupta: client user of C01, Client Viewer
    grants.append(Grant(
        id="grt-rajesh-client-viewer", user_id="rajesh-gupta", role_id="client_viewer", client_id="C01",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Client user portal access for C01", batch_id="b-rajesh"
    ))

    # 19. Sneha Kapoor: client user of C06, Client Viewer
    grants.append(Grant(
        id="grt-sneha-client-viewer", user_id="sneha-kapoor", role_id="client_viewer", client_id="C06",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Client user portal access for C06", batch_id="b-sneha"
    ))

    # 20. overnight-parser: system user with Parser role
    grants.append(Grant(
        id="grt-parser-system", user_id="overnight-parser", role_id="parser",
        effect="allow", valid_from=t_start, granted_by="om-agrawal", created_at=t_start,
        reason="Automated EDI ingestion agent", batch_id="b-parser"
    ))

    # 21. Zoya Ansari: new joiner (zero grants)

    db.add_all(grants)
    db.commit()

    print("Seeding showcase jobs and realistic workflow histories...")

    # Fixed Showcase Jobs:
    # 1. NF-SHOWCASE-FILED: FILED job in C01/Mumbai-Fort/IMPORT for cancel/reopen demo
    job_filed = Job(
        id="JOB-SHOWCASE-01",
        ref="NF-SHOWCASE-FILED",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="FILED",
        prepared_by="asha-rao",
        checked_by="rohit-mehta",
        filed_by="neha-kulkarni",
        cycle=1,
        internal_notes="High value pharmaceutical shipment; filed with Customs",
        created_by="overnight-parser",
        created_at=now - timedelta(days=15),
        updated_at=now - timedelta(days=10),
    )
    db.add(job_filed)

    # 2. NF-SHOWCASE-PREPARED-SOD: PREPARED job Asha prepared in C03 for SoD conflict
    job_sod = Job(
        id="JOB-SHOWCASE-02",
        ref="NF-SHOWCASE-PREPARED-SOD",
        client_id="C03",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="PREPARED",
        prepared_by="asha-rao",
        cycle=1,
        internal_notes="Asha prepared this shipment; SoD prevents her from checking it despite holding Checker for C03",
        created_by="overnight-parser",
        created_at=now - timedelta(days=3),
        updated_at=now - timedelta(days=2),
    )
    db.add(job_sod)

    # 3. NF-SHOWCASE-STUCK: Stuck PREPARED job at Delhi-ICD for Ops Admin override demo
    job_stuck = Job(
        id="JOB-SHOWCASE-03",
        ref="NF-SHOWCASE-STUCK",
        client_id="C05",
        branch_id="BR-DEL",
        direction="IMPORT",
        mode="FCL",
        stage="PREPARED",
        prepared_by="imran-shaikh",
        assigned_to="imran-shaikh",
        cycle=1,
        internal_notes="Prepared by Imran before going absent; requires Ops Admin override send-back or reassignment",
        created_by="overnight-parser",
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(days=4),
    )
    db.add(job_stuck)

    # 4. NF-SHOWCASE-ARJUN-REVOKED: Job assigned to Arjun on C08 and auto-unassigned when grant was revoked yesterday
    job_arjun = Job(
        id="JOB-SHOWCASE-04",
        ref="NF-SHOWCASE-ARJUN-REVOKED",
        client_id="C08",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="PREPARED",
        prepared_by="asha-rao",
        assigned_to=None,  # Was arjun-reddy, unassigned upon revocation
        cycle=1,
        internal_notes="Returned to pool when Arjun Reddy's Checker grant was revoked",
        created_by="overnight-parser",
        created_at=now - timedelta(days=4),
        updated_at=now - timedelta(days=1),
    )
    db.add(job_arjun)

    # Add audit log for Arjun's auto-unassign
    db.add(AuditLog(
        at=now - timedelta(days=1),
        actor_id="om-agrawal",
        actor_type="staff",
        event_type="AUTO_UNASSIGNED",
        action="auto_unassign",
        decision="EXECUTE",
        job_id="JOB-SHOWCASE-04",
        target_user_id="arjun-reddy",
        reason_codes=["ROLE_OR_STATUS_CHANGED", "NO_GRANT"],
        before_state={"assigned_to": "arjun-reddy", "stage": "PREPARED"},
        after_state={"assigned_to": None, "stage": "PREPARED"},
    ))

    # Audit events for the historical "who could have changed it on the 3rd" demo (~30 days ago)
    t_demo_historical = now - timedelta(days=32)
    job_hist_demo = Job(
        id="JOB-HIST-DEMO-01",
        ref="NF-IMP-AIR-OCT03",
        client_id="C01",
        branch_id="BR-MUM",
        direction="IMPORT",
        mode="AIR",
        stage="FILED",
        prepared_by="asha-rao",
        checked_by="rohit-mehta",
        filed_by="neha-kulkarni",
        cycle=1,
        internal_notes="Historical audit demonstration shipment",
        created_by="overnight-parser",
        created_at=t_demo_historical,
        updated_at=t_demo_historical + timedelta(hours=6),
    )
    db.add(job_hist_demo)

    db.add(AuditLog(
        at=t_demo_historical,
        actor_id="overnight-parser",
        actor_type="system",
        actor_run_id="RUN-20261003",
        event_type="JOB_CREATE",
        action="create",
        decision="EXECUTE",
        job_id="JOB-HIST-DEMO-01",
        after_state={"stage": "CONFIRMED"},
    ))
    db.add(AuditLog(
        at=t_demo_historical + timedelta(hours=2),
        actor_id="asha-rao",
        actor_type="staff",
        event_type="JOB_ACTION",
        action="prepare",
        decision="EXECUTE",
        job_id="JOB-HIST-DEMO-01",
        before_state={"stage": "CONFIRMED"},
        after_state={"stage": "PREPARED", "prepared_by": "asha-rao"},
    ))
    db.add(AuditLog(
        at=t_demo_historical + timedelta(hours=4),
        actor_id="rohit-mehta",
        actor_type="staff",
        event_type="JOB_ACTION",
        action="check",
        decision="EXECUTE",
        job_id="JOB-HIST-DEMO-01",
        before_state={"stage": "PREPARED"},
        after_state={"stage": "CHECKED", "checked_by": "rohit-mehta"},
    ))
    db.add(AuditLog(
        at=t_demo_historical + timedelta(hours=6),
        actor_id="neha-kulkarni",
        actor_type="staff",
        event_type="JOB_ACTION",
        action="file",
        decision="EXECUTE",
        job_id="JOB-HIST-DEMO-01",
        before_state={"stage": "CHECKED"},
        after_state={"stage": "FILED", "filed_by": "neha-kulkarni"},
    ))

    # Generate remaining ~295 realistic jobs across dimensions and stages
    stages = ["CONFIRMED", "PREPARED", "CHECKED", "FILED", "CANCELLED", "REOPENED"]
    directions = ["IMPORT", "EXPORT"]
    modes = ["AIR", "FCL", "LCL"]
    branch_ids = [b.id for b in branches]
    client_ids = [c.id for c in clients]

    print("Generating batch of 295 operational jobs...")
    for idx in range(1, 296):
        c_id = random.choice(client_ids)
        b_id = random.choice(branch_ids)
        dir_val = random.choice(directions)
        mode_val = random.choice(modes)
        stage_val = random.choice(stages)

        # Stagger creation times over the last 30 days
        days_ago = random.uniform(0.5, 30.0)
        job_created_at = now - timedelta(days=days_ago)
        job_updated_at = job_created_at + timedelta(hours=random.uniform(1.0, 12.0))

        prep_by = None
        chk_by = None
        fld_by = None
        assigned = None

        if stage_val in ("PREPARED", "CHECKED", "FILED"):
            prep_by = "asha-rao"
        if stage_val in ("CHECKED", "FILED"):
            chk_by = "priya-nair"
        if stage_val == "FILED":
            fld_by = "neha-kulkarni"

        # Assign some uncompleted jobs
        if stage_val in ("CONFIRMED", "PREPARED", "CHECKED", "REOPENED"):
            if random.random() < 0.4:
                assigned = random.choice(["asha-rao", "priya-nair", "pooja-sharma", "karan-shah"])

        job_row = Job(
            id=f"JOB-SEED-{idx:04d}",
            ref=f"NF-{dir_val[:3]}-{mode_val[:3]}-{idx:06d}",
            client_id=c_id,
            branch_id=b_id,
            direction=dir_val,
            mode=mode_val,
            stage=stage_val,
            assigned_to=assigned,
            prepared_by=prep_by,
            checked_by=chk_by,
            filed_by=fld_by,
            cycle=1,
            internal_notes=f"Operational customs manifest {idx}",
            created_by="overnight-parser",
            created_at=job_created_at,
            updated_at=job_updated_at,
        )
        db.add(job_row)

        # Add corresponding audit log events
        db.add(AuditLog(
            at=job_created_at,
            actor_id="overnight-parser",
            actor_type="system",
            actor_run_id=f"RUN-{job_created_at.strftime('%Y%m%d')}",
            event_type="JOB_CREATE",
            action="create",
            decision="EXECUTE",
            job_id=job_row.id,
            after_state={"stage": "CONFIRMED"},
        ))

        if prep_by:
            db.add(AuditLog(
                at=job_created_at + timedelta(hours=1),
                actor_id=prep_by,
                actor_type="staff",
                event_type="JOB_ACTION",
                action="prepare",
                decision="EXECUTE",
                job_id=job_row.id,
                before_state={"stage": "CONFIRMED"},
                after_state={"stage": "PREPARED", "prepared_by": prep_by},
            ))

        if chk_by:
            db.add(AuditLog(
                at=job_created_at + timedelta(hours=3),
                actor_id=chk_by,
                actor_type="staff",
                event_type="JOB_ACTION",
                action="check",
                decision="EXECUTE",
                job_id=job_row.id,
                before_state={"stage": "PREPARED"},
                after_state={"stage": "CHECKED", "checked_by": chk_by},
            ))

        if fld_by:
            db.add(AuditLog(
                at=job_created_at + timedelta(hours=5),
                actor_id=fld_by,
                actor_type="staff",
                event_type="JOB_ACTION",
                action="file",
                decision="EXECUTE",
                job_id=job_row.id,
                before_state={"stage": "CHECKED"},
                after_state={"stage": "FILED", "filed_by": fld_by},
            ))

    db.commit()
    total_jobs = db.query(Job).count()
    total_users = db.query(User).count()
    total_grants = db.query(Grant).count()
    total_audits = db.query(AuditLog).count()
    db.close()

    print("\nDatabase seeded successfully!")
    print(f"Total Users:  {total_users}")
    print(f"Total Grants: {total_grants}")
    print(f"Total Jobs:   {total_jobs}")
    print(f"Total Audits: {total_audits}")


if __name__ == "__main__":
    seed()
