/**
 * Nagarkot Access Control Service - Plain-English Label Dictionary
 * Maps internal technical codes, enums, and decision outcomes to clear human sentences.
 */

export const REASON_LABELS = {
  // Decision engine primary reasons and check codes
  USER_UNKNOWN: "User is not recognized in the directory or credentials are invalid.",
  USER_ABSENT: "User is currently marked absent. Operational rights are suspended while absent.",
  CLIENT_USER_RESTRICTED: "Client user account is restricted strictly to read-only shipment tracking.",
  SYSTEM_USER_RESTRICTED: "Automated system user can only create or update unfiled shipments.",
  INCOMPLETE_JOB_DATA: "Shipment data is missing required dimensions (Client, Branch, Direction, or Mode).",
  UNKNOWN_ACTION: "The requested operation does not exist in the service permissions catalogue.",
  STAGE_INVALID: "Shipment stage does not allow this action (e.g. cannot check an unconfirmed or already filed job).",
  NO_GRANT: "No active access grant matches this action and shipment scope (Client, Branch, Direction, Mode).",
  GRANT_COVERS_SCOPE: "Operational grant does not cover this specific client, branch, direction, or mode.",
  DENY_OVERRIDE: "Access is explicitly denied by an overriding compliance restriction (Deny Precedence).",
  SOD_VIOLATION_MAKER_CHECKER: "Separation of Duties: You prepared this checklist, so the four-eyes rule prohibits you from checking it.",
  SOD_VIOLATION_SELF_APPROVAL: "Separation of Duties: You submitted this sensitive request, so you cannot approve your own action.",
  REASON_REQUIRED: "A mandatory written justification is required for this sensitive or override operation.",
  NEEDS_APPROVAL: "Two-Person Rule: Modifying a filed shipment requires formal Compliance Approver review.",
  INDETERMINATE: "The authorization engine encountered an indeterminate state and failed closed safely.",
  LOCKOUT_PREVENTED: "Action blocked: Revoking this administrator would leave the company with zero active super administrators.",
  SCOPE_CONTAINMENT_VIOLATION: "Grant scope cannot be broader than the administrator's own authorized scope.",
  PRIVILEGED_ROLE_DENIED: "Only Super Administrators can assign or modify privileged administrative roles.",
  SELF_REVOCATION_DENIED: "Administrators cannot revoke their own access grants.",
  SELF_GRANT_DENIED: "Administrators cannot assign new permissions or grants to themselves.",
};

export const STAGE_CONFIG = {
  CONFIRMED: { label: "Confirmed", description: "Booking confirmed; awaiting checklist preparation", badgeClass: "badge-confirmed" },
  PREPARED: { label: "Prepared", description: "Checklist drafted; awaiting independent verification", badgeClass: "badge-prepared" },
  CHECKED: { label: "Checked", description: "Verified & approved; ready for customs filing", badgeClass: "badge-checked" },
  FILED: { label: "Filed", description: "Statutory Bill of Entry / Shipping Bill filed with Customs", badgeClass: "badge-filed" },
  CANCELLED: { label: "Cancelled", description: "Shipment cancelled before filing", badgeClass: "badge-cancelled" },
  REOPENED: { label: "Reopened", description: "Filed shipment reopened after authorized compliance approval", badgeClass: "badge-reopened" },
};

export const ACTION_CONFIG = {
  prepare: { label: "Prepare Checklist", badgeClass: "btn-action-primary", verb: "preparing" },
  check: { label: "Check & Verify", badgeClass: "btn-action-primary", verb: "checking" },
  file: { label: "File to Customs", badgeClass: "btn-action-primary", verb: "filing" },
  cancel: { label: "Cancel Job", badgeClass: "btn-action-danger", verb: "cancelling" },
  cancel_filed: { label: "Request Cancellation (Filed)", badgeClass: "btn-action-warning", verb: "requesting cancellation" },
  reopen: { label: "Request Reopen", badgeClass: "btn-action-warning", verb: "requesting reopen" },
  reassign: { label: "Reassign Assignee", badgeClass: "btn-action-secondary", verb: "reassigning" },
  override_send_back: { label: "Admin Rollback (Send Back)", badgeClass: "btn-action-danger", verb: "rolling back" },
};

export const OUTCOME_CONFIG = {
  ALLOW: { label: "Allowed", badgeClass: "badge-allow", icon: "✓" },
  DENY: { label: "Denied", badgeClass: "badge-deny", icon: "✕" },
  NEEDS_APPROVAL: { label: "Needs Approval", badgeClass: "badge-approval", icon: "⏳" },
};

/**
 * Returns a human-friendly sentence for any raw reason code.
 */
export function getFriendlyReason(code, fallback = "Action cannot be performed under current policies.") {
  if (!code) return "";
  return REASON_LABELS[code] || code.replace(/_/g, " ").toLowerCase();
}

/**
 * Returns friendly stage label and badge class.
 */
export function getStageMeta(stage) {
  return STAGE_CONFIG[stage] || { label: stage || "Unknown", description: "", badgeClass: "badge-neutral" };
}

/**
 * Returns friendly action meta.
 */
export function getActionMeta(action) {
  return ACTION_CONFIG[action] || { label: action, badgeClass: "btn-action-secondary", verb: action };
}

/**
 * Format relative time ("2 hours ago", "just now")
 */
export function formatRelativeTime(dateInput) {
  if (!dateInput) return "—";
  const date = new Date(dateInput);
  const now = new Date();
  const diffSec = Math.floor((now - date) / 1000);

  if (diffSec < 45) return "just now";
  if (diffSec < 90) return "1 min ago";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} mins ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours} hr${diffHours > 1 ? "s" : ""} ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/**
 * Format absolute local datetime with timezone
 */
export function formatFullDateTime(dateInput) {
  if (!dateInput) return "—";
  const d = new Date(dateInput);
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
