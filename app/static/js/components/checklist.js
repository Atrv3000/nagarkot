/**
 * Nagarkot Access Control Service - Decision Checklist Component
 * Renders the deterministic 8-stage decision pipeline checks with plain-English details.
 */

import { getFriendlyReason } from "../labels.js";

export function createDecisionChecklist(decision) {
  const container = document.createElement("div");
  container.className = "decision-checklist-container";

  if (!decision || !decision.checks) {
    container.textContent = "No decision checks available.";
    return container;
  }

  // Summary Banner
  const summary = document.createElement("div");
  const isAllow = decision.allowed;
  const isApproval = decision.outcome === "NEEDS_APPROVAL";

  summary.className = `decision-summary-banner ${isAllow ? 'summary-allow' : (isApproval ? 'summary-approval' : 'summary-deny')}`;

  const outcomeTitle = document.createElement("h4");
  outcomeTitle.style.fontSize = "15px";
  outcomeTitle.style.fontWeight = "700";
  outcomeTitle.style.marginBottom = "4px";
  outcomeTitle.textContent = `Outcome: ${decision.outcome} (${isAllow ? 'Operation Allowed' : (isApproval ? 'Two-Person Approval Required' : 'Operation Denied')})`;

  const outcomeDesc = document.createElement("p");
  outcomeDesc.style.fontSize = "13px";
  if (decision.primary_reason) {
    outcomeDesc.textContent = `Primary Reason: ${getFriendlyReason(decision.primary_reason)} [${decision.primary_reason}]`;
  } else {
    outcomeDesc.textContent = "All 8 pipeline authorization checks passed successfully.";
  }

  summary.appendChild(outcomeTitle);
  summary.appendChild(outcomeDesc);
  container.appendChild(summary);

  // Checks List
  const list = document.createElement("div");
  list.className = "checklist-items";

  let firstFailingFound = false;

  decision.checks.forEach((chk, idx) => {
    const item = document.createElement("div");
    const isPass = chk.passed;
    const isFirstFailing = !isPass && !firstFailingFound;

    if (isFirstFailing) {
      firstFailingFound = true;
    }

    item.className = `checklist-item ${isPass ? 'check-pass' : 'check-fail'} ${isFirstFailing ? 'check-primary-failure' : ''}`;

    const icon = document.createElement("div");
    icon.className = `check-icon ${isPass ? 'check-icon-pass' : 'check-icon-fail'}`;
    icon.textContent = isPass ? "✓" : "✕";

    const content = document.createElement("div");
    content.className = "check-content";

    const header = document.createElement("div");
    header.className = "check-header";

    const title = document.createElement("span");
    title.className = "check-code";
    title.textContent = `${idx + 1}. ${chk.code}`;

    const tag = document.createElement("span");
    tag.className = `badge ${isPass ? 'badge-allow' : 'badge-deny'}`;
    tag.textContent = isPass ? "PASSED" : (isFirstFailing ? "FAILING (BLOCKING)" : "FAILED");

    header.appendChild(title);
    header.appendChild(tag);

    const detail = document.createElement("div");
    detail.className = "check-detail";
    detail.textContent = chk.detail;

    content.appendChild(header);
    content.appendChild(detail);

    item.appendChild(icon);
    item.appendChild(content);
    list.appendChild(item);
  });

  container.appendChild(list);

  // Matched / Denying Grants Box
  if ((decision.matched_grants && decision.matched_grants.length > 0) || (decision.denying_grants && decision.denying_grants.length > 0)) {
    const grantsBox = document.createElement("div");
    grantsBox.className = "checklist-grants-box";

    if (decision.matched_grants && decision.matched_grants.length > 0) {
      const p = document.createElement("div");
      const strong = document.createElement("strong");
      strong.textContent = "Matched Allow Grants: ";
      p.appendChild(strong);
      p.appendChild(document.createTextNode(decision.matched_grants.join(", ")));
      grantsBox.appendChild(p);
    }
    if (decision.denying_grants && decision.denying_grants.length > 0) {
      const p = document.createElement("div");
      p.style.color = "var(--danger-text)";
      p.style.marginTop = "6px";
      const strong = document.createElement("strong");
      strong.textContent = "Overriding Deny Grants: ";
      p.appendChild(strong);
      p.appendChild(document.createTextNode(decision.denying_grants.join(", ")));
      grantsBox.appendChild(p);
    }
    container.appendChild(grantsBox);
  }

  return container;
}
