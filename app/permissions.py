"""Fixed permission catalogue and privilege evaluation logic."""
from typing import Iterable, Set

# Fixed catalogue defined in code
JOB_VIEW = "job.view"
JOB_VIEW_INTERNAL = "job.view_internal"
JOB_CREATE = "job.create"
JOB_UPDATE_UNFILED = "job.update_unfiled"
JOB_PREPARE = "job.prepare"
JOB_CHECK = "job.check"
JOB_FILE = "job.file"
JOB_CANCEL = "job.cancel"
JOB_CANCEL_FILED = "job.cancel_filed"
JOB_REOPEN = "job.reopen"
JOB_APPROVE_SENSITIVE = "job.approve_sensitive"
JOB_REASSIGN = "job.reassign"
JOB_OVERRIDE = "job.override"

ACCESS_MANAGE = "access.manage"
ACCESS_MANAGE_PRIVILEGED = "access.manage_privileged"
ROLES_MANAGE = "roles.manage"
AUDIT_VIEW = "audit.view"

ALL_PERMISSIONS: Set[str] = {
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
}

# Action to required permission mapping
ACTION_TO_PERMISSION = {
    "view": JOB_VIEW,
    "view_internal": JOB_VIEW_INTERNAL,
    "create": JOB_CREATE,
    "update_unfiled": JOB_UPDATE_UNFILED,
    "prepare": JOB_PREPARE,
    "check": JOB_CHECK,
    "file": JOB_FILE,
    "cancel": JOB_CANCEL,
    "cancel_filed": JOB_CANCEL_FILED,
    "reopen": JOB_REOPEN,
    "approve_sensitive": JOB_APPROVE_SENSITIVE,
    "reassign": JOB_REASSIGN,
    "override_send_back": JOB_OVERRIDE,
}


def is_privileged_permission(permission: str) -> bool:
    """A permission is privileged if it modifies security policy or overrides business rules."""
    return (
        permission.startswith("access.")
        or permission in {ROLES_MANAGE, JOB_OVERRIDE, JOB_APPROVE_SENSITIVE}
    )


def is_privileged_role(permissions: Iterable[str]) -> bool:
    """A role is privileged if it contains at least one privileged permission."""
    return any(is_privileged_permission(p) for p in permissions)
