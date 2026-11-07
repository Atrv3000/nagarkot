/**
 * Nagarkot Access Control Service - Audit Trail View
 * Displays immutable audit events with filterable parameters and expandable decision details.
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { formatFullDateTime } from "../labels.js";

export async function renderAuditPage(container) {
  document.getElementById("view-heading").textContent = "Immutable Compliance Audit Trail";
  container.innerHTML = "";

  const card = document.createElement("div");
  card.className = "card";

  const header = document.createElement("div");
  header.className = "card-header";

  const titleGroup = document.createElement("div");
  const title = document.createElement("h2");
  title.className = "card-title";
  title.textContent = "Audit Trail & Tamper-Evident Log";

  const sub = document.createElement("div");
  sub.className = "card-subtitle";
  sub.id = "audit-subtitle";
  sub.textContent = "All actions, state transitions, administrative grants, and denied attempts are immutably logged.";

  titleGroup.appendChild(title);
  titleGroup.appendChild(sub);
  header.appendChild(titleGroup);

  const body = document.createElement("div");
  body.className = "card-body";

  // Filter Bar
  const filterForm = document.createElement("div");
  filterForm.style.display = "grid";
  filterForm.style.gridTemplateColumns = "repeat(auto-fit, minmax(180px, 1fr))";
  filterForm.style.gap = "12px";
  filterForm.style.padding = "16px";
  filterForm.style.backgroundColor = "var(--bg-app)";
  filterForm.style.borderRadius = "var(--radius-md)";
  filterForm.style.marginBottom = "20px";
  filterForm.style.border = "1px solid var(--border-color)";

  // Job ID filter
  const fJobGroup = document.createElement("div");
  fJobGroup.className = "form-group";
  fJobGroup.style.marginBottom = "0";
  const fJobLabel = document.createElement("label");
  fJobLabel.className = "form-label";
  fJobLabel.textContent = "Filter by Job ID:";
  const fJobInput = document.createElement("input");
  fJobInput.className = "form-input";
  fJobInput.placeholder = "e.g. JOB-SHOWCASE-01";
  fJobGroup.appendChild(fJobLabel);
  fJobGroup.appendChild(fJobInput);

  // Actor ID filter
  const fActorGroup = document.createElement("div");
  fActorGroup.className = "form-group";
  fActorGroup.style.marginBottom = "0";
  const fActorLabel = document.createElement("label");
  fActorLabel.className = "form-label";
  fActorLabel.textContent = "Filter by Actor:";
  const fActorInput = document.createElement("input");
  fActorInput.className = "form-input";
  fActorInput.placeholder = "e.g. asha-rao, om-agrawal";
  fActorGroup.appendChild(fActorLabel);
  fActorGroup.appendChild(fActorInput);

  // Event Type filter
  const fEventGroup = document.createElement("div");
  fEventGroup.className = "form-group";
  fEventGroup.style.marginBottom = "0";
  const fEventLabel = document.createElement("label");
  fEventLabel.className = "form-label";
  fEventLabel.textContent = "Event Type:";
  const fEventSelect = document.createElement("select");
  fEventSelect.className = "form-select";
  fEventSelect.innerHTML = `
    <option value="">ALL Event Types</option>
    <option value="JOB_ACTION">JOB_ACTION</option>
    <option value="DENIED_ATTEMPT">DENIED_ATTEMPT</option>
    <option value="APPROVAL_REQUESTED">APPROVAL_REQUESTED</option>
    <option value="APPROVAL_DECISION">APPROVAL_DECISION</option>
    <option value="USER_STATUS_CHANGE">USER_STATUS_CHANGE</option>
    <option value="GRANT_CREATE">GRANT_CREATE</option>
    <option value="GRANT_REVOKE">GRANT_REVOKE</option>
    <option value="JOB_OVERRIDE">JOB_OVERRIDE</option>
  `;
  fEventGroup.appendChild(fEventLabel);
  fEventGroup.appendChild(fEventSelect);

  // Limit filter
  const fLimitGroup = document.createElement("div");
  fLimitGroup.className = "form-group";
  fLimitGroup.style.marginBottom = "0";
  const fLimitLabel = document.createElement("label");
  fLimitLabel.className = "form-label";
  fLimitLabel.textContent = "Limit Rows:";
  const fLimitSelect = document.createElement("select");
  fLimitSelect.className = "form-select";
  fLimitSelect.innerHTML = `
    <option value="25">25 records</option>
    <option value="50" selected>50 records</option>
    <option value="100">100 records</option>
  `;
  fLimitGroup.appendChild(fLimitLabel);
  fLimitGroup.appendChild(fLimitSelect);

  filterForm.appendChild(fJobGroup);
  filterForm.appendChild(fActorGroup);
  filterForm.appendChild(fEventGroup);
  filterForm.appendChild(fLimitGroup);

  const filterBtnGroup = document.createElement("div");
  filterBtnGroup.style.gridColumn = "1 / -1";
  filterBtnGroup.style.display = "flex";
  filterBtnGroup.style.justifyContent = "flex-end";
  filterBtnGroup.style.gap = "10px";

  const resetBtn = document.createElement("button");
  resetBtn.className = "btn btn-secondary";
  resetBtn.textContent = "Reset Filters";
  resetBtn.onclick = () => {
    fJobInput.value = "";
    fActorInput.value = "";
    fEventSelect.value = "";
    fLimitSelect.value = "50";
    loadAuditTrail(tableBody, sub, {});
  };

  const applyBtn = document.createElement("button");
  applyBtn.className = "btn btn-primary";
  applyBtn.textContent = "Apply Audit Filters";
  applyBtn.onclick = () => {
    const params = {
      limit: fLimitSelect.value,
    };
    if (fJobInput.value.trim()) params.job_id = fJobInput.value.trim();
    if (fActorInput.value.trim()) params.actor_id = fActorInput.value.trim();
    if (fEventSelect.value) params.event_type = fEventSelect.value;
    loadAuditTrail(tableBody, sub, params);
  };

  filterBtnGroup.appendChild(resetBtn);
  filterBtnGroup.appendChild(applyBtn);
  filterForm.appendChild(filterBtnGroup);
  body.appendChild(filterForm);

  // Table
  const tableWrapper = document.createElement("div");
  tableWrapper.className = "table-container";

  const table = document.createElement("table");
  table.className = "data-table";

  const thead = document.createElement("thead");
  thead.innerHTML = `
    <tr>
      <th style="width: 40px;"></th>
      <th>Timestamp</th>
      <th>Event Type</th>
      <th>Actor</th>
      <th>Target (Job / User)</th>
      <th>Action</th>
      <th>Decision</th>
    </tr>
  `;
  table.appendChild(thead);

  const tableBody = document.createElement("tbody");
  table.appendChild(tableBody);
  tableWrapper.appendChild(table);
  body.appendChild(tableWrapper);

  card.appendChild(header);
  card.appendChild(body);
  container.appendChild(card);

  loadAuditTrail(tableBody, sub, { limit: 50 });
}

async function loadAuditTrail(tbody, subtitleEl, params) {
  tbody.innerHTML = `
    <tr>
      <td colspan="7" style="padding: 32px; text-align: center;">
        <div class="skeleton" style="width: 50%; margin: 0 auto;"></div>
      </td>
    </tr>
  `;

  try {
    const records = await api.get("/audit", params);
    subtitleEl.textContent = `Displaying ${records.length} audit trail records (Protected by SQLite ABORT triggers)`;
    tbody.innerHTML = "";

    if (records.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="empty-state-card" style="border: none;">
              <h3>No Audit Records Found</h3>
              <p>No audit events match the specified filter criteria.</p>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    records.forEach(r => {
      const row = document.createElement("tr");

      // Expand toggle
      const tdExpand = document.createElement("td");
      const expandBtn = document.createElement("button");
      expandBtn.className = "btn btn-secondary";
      expandBtn.style.padding = "2px 6px";
      expandBtn.style.fontSize = "11px";
      expandBtn.textContent = "▶";
      tdExpand.appendChild(expandBtn);

      // Timestamp
      const tdTime = document.createElement("td");
      tdTime.style.fontSize = "12px";
      tdTime.textContent = formatFullDateTime(r.at);

      // Event Type
      const tdType = document.createElement("td");
      tdType.style.fontWeight = "600";
      tdType.textContent = r.event_type;
      if (r.is_override) {
        const ovr = document.createElement("span");
        ovr.className = "badge badge-warning";
        ovr.style.marginLeft = "6px";
        ovr.textContent = "Override";
        tdType.appendChild(ovr);
      }

      // Actor
      const tdActor = document.createElement("td");
      tdActor.textContent = `${r.actor_id} (${r.actor_type})`;

      // Target
      const tdTarget = document.createElement("td");
      if (r.job_id) {
        const jLink = document.createElement("a");
        jLink.href = `#/jobs/${r.job_id}`;
        jLink.style.color = "var(--primary)";
        jLink.style.fontWeight = "600";
        jLink.textContent = r.job_id;
        tdTarget.appendChild(jLink);
      } else if (r.target_user_id) {
        tdTarget.textContent = `User: ${r.target_user_id}`;
      } else {
        tdTarget.textContent = "—";
      }

      // Action
      const tdAction = document.createElement("td");
      tdAction.textContent = r.action;

      // Decision
      const tdDecision = document.createElement("td");
      const decBadge = document.createElement("span");
      if (r.decision === "ALLOW" || r.decision === "EXECUTE") {
        decBadge.className = "badge badge-allow";
      } else if (r.decision === "DENY") {
        decBadge.className = "badge badge-deny";
      } else if (r.decision === "NEEDS_APPROVAL") {
        decBadge.className = "badge badge-approval";
      } else {
        decBadge.className = "badge badge-neutral";
      }
      decBadge.textContent = r.decision;
      tdDecision.appendChild(decBadge);

      row.appendChild(tdExpand);
      row.appendChild(tdTime);
      row.appendChild(tdType);
      row.appendChild(tdActor);
      row.appendChild(tdTarget);
      row.appendChild(tdAction);
      row.appendChild(tdDecision);

      tbody.appendChild(row);

      // Expandable Detail Row
      const detailRow = document.createElement("tr");
      detailRow.style.display = "none";
      detailRow.style.backgroundColor = "var(--bg-app)";

      const detailTd = document.createElement("td");
      detailTd.colSpan = 7;
      detailTd.style.padding = "14px 20px";

      const detailBox = document.createElement("div");
      detailBox.style.fontSize = "12px";
      detailBox.style.lineHeight = "1.5";

      let parts = [];
      if (r.reason_codes && r.reason_codes.length > 0) {
        parts.push(`<div><strong>Reason Codes:</strong> <span style="color: var(--danger-text);">${r.reason_codes.join(', ')}</span></div>`);
      }
      if (r.grant_ids_used && r.grant_ids_used.length > 0) {
        parts.push(`<div><strong>Grants Utilized:</strong> ${r.grant_ids_used.join(', ')}</div>`);
      }
      if (r.before_state) {
        parts.push(`<div><strong>Before State:</strong> <code>${JSON.stringify(r.before_state)}</code></div>`);
      }
      if (r.after_state) {
        parts.push(`<div><strong>After State:</strong> <code>${JSON.stringify(r.after_state)}</code></div>`);
      }

      detailBox.innerHTML = parts.join("") || "<em>No additional state payload stored for this audit event.</em>";
      detailTd.appendChild(detailBox);
      detailRow.appendChild(detailTd);
      tbody.appendChild(detailRow);

      expandBtn.onclick = () => {
        if (detailRow.style.display === "none") {
          detailRow.style.display = "table-row";
          expandBtn.textContent = "▼";
        } else {
          detailRow.style.display = "none";
          expandBtn.textContent = "▶";
        }
      };
    });
  } catch (err) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="empty-state-card" style="border: none;">
            <h3>Audit Access Restricted</h3>
            <p>${err.message || 'Viewing the audit log requires audit.view permission. Switch to Om Agrawal (Super Admin) or Meera Iyer (Ops Admin) above.'}</p>
          </div>
        </td>
      </tr>
    `;
  }
}
