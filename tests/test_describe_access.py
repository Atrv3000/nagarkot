import io
import contextlib
from sqlalchemy.orm import Session
from scripts.describe_access import describe_all_users


def test_describe_all_users_output_integrity(seeded_db: Session):
    """Verify describe_all_users() produces expected plain-English lines for all personas."""
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        describe_all_users(seeded_db)
    output = f.getvalue()

    # Precondition: 21 users evaluated
    assert "Total Directory Users Evaluated: 21" in output

    # Check key persona assertions
    assert "Asha Rao (ID: asha-rao) - Type: STAFF [ACTIVE]" in output
    assert "[ALLOW] Role: 'maker' on (Client: ALL, Branch: ALL, Direction: ALL, Mode: ALL)" in output
    assert "[ALLOW] Role: 'checker' on (Client: C03, Branch: ALL, Direction: ALL, Mode: ALL)" in output

    assert "Rohit Mehta (ID: rohit-mehta) - Type: STAFF [ACTIVE]" in output
    assert "[ALLOW] Role: 'checker' on (Client: C01, Branch: BR-MUM, Direction: IMPORT, Mode: ALL)" in output

    assert "Imran Shaikh (ID: imran-shaikh) - Type: STAFF [ABSENT - SUSPENDED]" in output
    assert "User is currently marked ABSENT: all active operational permissions suspended" in output

    assert "Pooja Sharma (ID: pooja-sharma) - Type: STAFF [ACTIVE]" in output
    assert "(Absence cover for imran-shaikh)" in output

    assert "Tarun Das (ID: tarun-das) - Type: STAFF [ACTIVE]" in output
    assert "[DENY] Role: 'maker' on (Client: C04, Branch: ALL, Direction: ALL, Mode: ALL)" in output

    assert "Arjun Reddy (ID: arjun-reddy) - Type: STAFF [ACTIVE]" in output
    assert "No active grants assigned (Zero-trust default: all operations denied)" in output

    assert "Rajesh Gupta (ID: rajesh-gupta) - Type: CLIENT [ACTIVE]" in output
    assert "Assigned Organization Client ID: C01" in output
    assert "[ALLOW] Role: 'client_viewer' on (Client: C01, Branch: ALL, Direction: ALL, Mode: ALL)" in output

    assert "Zoya Ansari (ID: zoya-ansari) - Type: STAFF [ACTIVE]" in output
