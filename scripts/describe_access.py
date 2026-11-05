"""Inspect and print plain-English access descriptions for all directory personas."""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Optional
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import User
from app.grants import describe_user_access


def describe_all_users(db: Optional[Session] = None):
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    users = db.query(User).order_by(User.type.desc(), User.id.asc()).all()

    print("=" * 80)
    print(" NAGARKOT FORWARDERS PVT. LTD. - ACCESS DIRECTORY & CAPABILITY MATRIX")
    print("=" * 80)

    for idx, u in enumerate(users, 1):
        summary = describe_user_access(db, u.id)
        status_tag = f"[{u.status.upper()}]" if u.status == "active" else f"[{u.status.upper()} - SUSPENDED]"
        print(f"\n{idx:02d}. {u.name} (ID: {u.id}) - Type: {u.type.upper()} {status_tag}")
        if u.client_id:
            print(f"    Assigned Organization Client ID: {u.client_id}")

        if not summary.plain_english_rules:
            print("    * No active grants assigned (Zero-trust default: all operations denied)")
        else:
            for rule in summary.plain_english_rules:
                print(f"    * {rule}")

    print("\n" + "=" * 80)
    print(f" Total Directory Users Evaluated: {len(users)}")
    print("=" * 80)
    if close_db:
        db.close()


if __name__ == "__main__":
    describe_all_users()
