/**
 * Nagarkot Access Control Service - Badge Component
 * Produces accessible, semantic badges for stages, outcomes, statuses, and scopes.
 */

import { STAGE_CONFIG, OUTCOME_CONFIG } from "../labels.js";

export function createStageBadge(stage) {
  const meta = STAGE_CONFIG[stage] || { label: stage || "Unknown", badgeClass: "badge-neutral" };
  const span = document.createElement("span");
  span.className = `badge ${meta.badgeClass}`;
  span.textContent = meta.label;
  if (meta.description) {
    span.title = meta.description;
  }
  return span;
}

export function createOutcomeBadge(outcome) {
  const meta = OUTCOME_CONFIG[outcome] || { label: outcome || "Unknown", badgeClass: "badge-neutral", icon: "" };
  const span = document.createElement("span");
  span.className = `badge ${meta.badgeClass}`;
  span.textContent = `${meta.icon ? meta.icon + " " : ""}${meta.label}`;
  return span;
}

export function createUserStatusBadge(status) {
  const span = document.createElement("span");
  if (status === "absent") {
    span.className = "badge badge-status-absent";
    span.textContent = "Absent";
    span.title = "Operational permissions suspended";
  } else {
    span.className = "badge badge-status-active";
    span.textContent = "Active";
  }
  return span;
}

export function createScopeChip(label, value) {
  const span = document.createElement("span");
  span.className = "scope-chip";

  const keySpan = document.createElement("span");
  keySpan.className = "scope-chip-label";
  keySpan.textContent = label + ":";

  const valSpan = document.createElement("span");
  valSpan.className = "scope-chip-value";
  valSpan.textContent = value || "ALL";

  span.appendChild(keySpan);
  span.appendChild(document.createTextNode(" "));
  span.appendChild(valSpan);
  return span;
}
