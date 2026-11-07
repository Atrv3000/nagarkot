/**
 * Nagarkot Access Control Service - Approvals Governance View
 * Lists sensitive action requests requiring two-person compliance authorization.
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { router } from "../router.js";
import { openModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import { formatRelativeTime, formatFullDateTime } from "../labels.js";
import { escapeHtml } from "../utils.js";

export async function renderApprovalsPage(container) {
  document.getElementById("view-heading").textContent = "Two-Person Compliance Approvals";
  container.innerHTML = "";

  const card = document.createElement("div");
  card.className = "card";

  const header = document.createElement("div");
  header.className = "card-header";

  const titleGroup = document.createElement("div");
  const title = document.createElement("h2");
  title.className = "card-title";
  title.textContent = "Pending Sensitive Authorizations";

  const sub = document.createElement("div");
  sub.className = "card-subtitle";
  sub.id = "approvals-subtitle";
  sub.textContent = "Loading pending approvals...";

  titleGroup.appendChild(title);
  titleGroup.appendChild(sub);

  const headerActions = document.createElement("div");
  headerActions.style.display = "flex";
  headerActions.style.gap = "10px";

  const statusFilter = document.createElement("select");
  statusFilter.className = "form-select";
  statusFilter.style.width = "auto";
  statusFilter.innerHTML = `
    <option value="pending" selected>Status: Pending</option>
    <option value="approved">Status: Approved</option>
    <option value="rejected">Status: Rejected</option>
    <option value="stale">Status: Stale</option>
  `;

  const refreshBtn = document.createElement("button");
  refreshBtn.className = "btn btn-secondary";
  refreshBtn.innerHTML = "<span>↻</span> Refresh";
  refreshBtn.onclick = () => loadApprovals(tableBody, sub, statusFilter.value);

  statusFilter.onchange = () => loadApprovals(tableBody, sub, statusFilter.value);

  headerActions.appendChild(statusFilter);
  headerActions.appendChild(refreshBtn);
  header.appendChild(titleGroup);
  header.appendChild(headerActions);

  const body = document.createElement("div");
  body.className = "card-body";

  const tableWrapper = document.createElement("div");
  tableWrapper.className = "table-container";

  const table = document.createElement("table");
  table.className = "data-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Approval ID", "Shipment Ref", "Action", "Requester", "Justification", "Submitted", "Governance Actions"].forEach(col => {
    const th = document.createElement("th");
    th.textContent = col;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);

  const tableBody = document.createElement("tbody");
  table.appendChild(thead);
  table.appendChild(tableBody);
  tableWrapper.appendChild(table);

  body.appendChild(tableWrapper);
  card.appendChild(header);
  card.appendChild(body);
  container.appendChild(card);

  await loadApprovals(tableBody, sub, "pending");
}

async function loadApprovals(tbody, subtitleEl, statusFilter) {
  tbody.innerHTML = `
    <tr>
      <td colspan="7" style="padding: 32px; text-align: center;">
        <div class="skeleton" style="width: 50%; margin: 0 auto;"></div>
      </td>
    </tr>
  `;

  try {
    const approvals = await api.get("/approvals", { status: statusFilter });
    subtitleEl.textContent = `${approvals.length} ${statusFilter} approval request${approvals.length === 1 ? '' : 's'}`;
    tbody.innerHTML = "";

    if (approvals.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="empty-state-card" style="border: none;">
              <h3>No ${escapeHtml(statusFilter.toUpperCase())} Approvals</h3>
              <p>There are no sensitive action requests in ${escapeHtml(statusFilter)} status.</p>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    const currentUserId = state.currentUser;
    const currentUserRole = state.currentUserObj?.role_label || "";
    // Only approvers and super admins hold job.approve_sensitive
    const isApproverQualified = currentUserRole.includes("Approver") || currentUserRole.includes("Super Admin");

    approvals.forEach(app => {
      const row = document.createElement("tr");

      // ID
      const tdId = document.createElement("td");
      tdId.style.fontWeight = "600";
      tdId.textContent = app.id;

      // Job Ref
      const tdJob = document.createElement("td");
      const jobLink = document.createElement("a");
      jobLink.href = `#/jobs/${encodeURIComponent(app.job_id)}`;
      jobLink.style.color = "var(--primary)";
      jobLink.style.fontWeight = "600";
      jobLink.textContent = app.job_id;
      tdJob.appendChild(jobLink);

      // Action
      const tdAction = document.createElement("td");
      const actBadge = document.createElement("span");
      actBadge.className = "badge badge-neutral";
      actBadge.textContent = app.action;
      tdAction.appendChild(actBadge);

      // Requester
      const tdReq = document.createElement("td");
      tdReq.textContent = app.requested_by;

      // Reason
      const tdReason = document.createElement("td");
      tdReason.style.maxWidth = "260px";
      tdReason.textContent = app.reason || "—";
      tdReason.title = app.reason || "";

      // Time
      const tdTime = document.createElement("td");
      tdTime.textContent = formatRelativeTime(app.created_at);
      tdTime.title = formatFullDateTime(app.created_at);

      // Actions
      const tdActions = document.createElement("td");

      if (app.status === "pending") {
        const isSelfRequester = currentUserId === app.requested_by;
        const canAct = isApproverQualified && !isSelfRequester;

        const actionGroup = document.createElement("div");
        actionGroup.style.display = "flex";
        actionGroup.style.gap = "6px";
        actionGroup.style.alignItems = "center";

        const approveBtn = document.createElement("button");
        approveBtn.className = "btn btn-success";
        approveBtn.style.padding = "4px 10px";
        approveBtn.style.fontSize = "12px";
        approveBtn.textContent = "Approve";
        approveBtn.disabled = !canAct;

        const rejectBtn = document.createElement("button");
        rejectBtn.className = "btn btn-danger";
        rejectBtn.style.padding = "4px 10px";
        rejectBtn.style.fontSize = "12px";
        rejectBtn.textContent = "Reject";
        rejectBtn.disabled = !canAct;

        if (isSelfRequester) {
          approveBtn.title = "Separation of Duties: You submitted this request, so you cannot approve it.";
          rejectBtn.title = approveBtn.title;
          const hint = document.createElement("span");
          hint.style.fontSize = "11px";
          hint.style.color = "var(--danger-text)";
          hint.textContent = "SoD Conflict (Self-Approval Denied)";
          actionGroup.appendChild(hint);
        } else if (!isApproverQualified) {
          approveBtn.title = "Only users with Compliance Approver permission (e.g. Sunita Patil) can approve sensitive actions.";
          rejectBtn.title = approveBtn.title;
          const hint = document.createElement("span");
          hint.style.fontSize = "11px";
          hint.style.color = "var(--text-muted)";
          hint.textContent = "Requires Compliance Approver";
          actionGroup.appendChild(hint);
        } else {
          approveBtn.onclick = () => handleDecision(app, "approve", tbody, subtitleEl, statusFilter);
          rejectBtn.onclick = () => handleDecision(app, "reject", tbody, subtitleEl, statusFilter);
          actionGroup.appendChild(approveBtn);
          actionGroup.appendChild(rejectBtn);
        }

        tdActions.appendChild(actionGroup);
      } else {
        const statusSpan = document.createElement("span");
        statusSpan.className = `badge ${app.status === 'approved' ? 'badge-allow' : 'badge-deny'}`;
        statusSpan.textContent = `${app.status.toUpperCase()} by ${app.decided_by || 'system'}`;
        tdActions.appendChild(statusSpan);
      }

      row.appendChild(tdId);
      row.appendChild(tdJob);
      row.appendChild(tdAction);
      row.appendChild(tdReq);
      row.appendChild(tdReason);
      row.appendChild(tdTime);
      row.appendChild(tdActions);

      tbody.appendChild(row);
    });
  } catch (err) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="error-state-card" style="border: none;">
            <h3>Error loading approvals</h3>
            <p>${escapeHtml(err.message || 'Unable to retrieve approval list.')}</p>
          </div>
        </td>
      </tr>
    `;
  }
}

function handleDecision(app, decisionType, tbody, subtitleEl, statusFilter) {
  const isApprove = decisionType === "approve";

  const form = document.createElement("div");
  const p = document.createElement("p");
  p.style.fontSize = "13px";
  p.style.marginBottom = "14px";
  p.textContent = `You are deciding to ${decisionType.toUpperCase()} request ${app.id} on shipment ${app.job_id} (${app.action}).`;
  form.appendChild(p);

  const group = document.createElement("div");
  group.className = "form-group";
  const lbl = document.createElement("label");
  lbl.className = "form-label";
  lbl.textContent = "Mandatory Approver Justification:";
  const textarea = document.createElement("textarea");
  textarea.className = "form-textarea";
  textarea.placeholder = "Enter reason for this compliance decision...";
  group.appendChild(lbl);
  group.appendChild(textarea);
  form.appendChild(group);

  openModal({
    title: `${isApprove ? 'Approve' : 'Reject'} Request: ${app.id}`,
    contentElement: form,
    confirmText: isApprove ? "Confirm Approval" : "Confirm Rejection",
    confirmClass: isApprove ? "btn-success" : "btn-danger",
    onConfirm: async () => {
      const reason = textarea.value.trim();
      if (reason.length < 3) {
        showToast("A valid written justification is required.", "warning");
        return false;
      }

      try {
        await api.post(`/approvals/${app.id}/${decisionType}`, { reason });
        showToast(`Request ${app.id} was successfully ${isApprove ? 'approved' : 'rejected'}.`, "success");
        loadApprovals(tbody, subtitleEl, statusFilter);
        return true;
      } catch (err) {
        showToast(err.message || `Failed to ${decisionType} approval.`, "error");
        return false;
      }
    },
  });
}
