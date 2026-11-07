/**
 * Nagarkot Access Control Service - Access Management View
 * Allows inspecting user permissions, active grants, revoking/creating grants, and toggling user absence status.
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { openModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import { createScopeChip, createUserStatusBadge } from "../components/badge.js";
import { formatFullDateTime } from "../labels.js";
import { escapeHtml } from "../utils.js";

export async function renderAccessPage(container) {
  document.getElementById("view-heading").textContent = "Access Directory & Capability Matrix";
  container.innerHTML = "";

  const card = document.createElement("div");
  card.className = "card";

  const header = document.createElement("div");
  header.className = "card-header";

  const titleGroup = document.createElement("div");
  const title = document.createElement("h2");
  title.className = "card-title";
  title.textContent = "Access Governance & Grant Manager";

  const sub = document.createElement("div");
  sub.className = "card-subtitle";
  sub.textContent = "Inspect plain-English rules, manage dimensional grants, and update absence status.";

  titleGroup.appendChild(title);
  titleGroup.appendChild(sub);

  const headerActions = document.createElement("div");
  headerActions.style.display = "flex";
  headerActions.style.gap = "10px";
  headerActions.style.alignItems = "center";

  const sweepBtn = document.createElement("button");
  sweepBtn.className = "btn btn-secondary";
  sweepBtn.textContent = "🧹 Sweep Expired Grants";
  sweepBtn.title = "Unassign in-flight jobs for users with expired grants";
  sweepBtn.onclick = async () => {
    try {
      sweepBtn.disabled = true;
      const resp = await api.post("/grants/sweep-expired");
      showToast(`Sweep completed: ${resp.unassigned_jobs_count} job(s) returned to pool.`, "success");
    } catch (err) {
      showToast(err.message || "Failed to run expired grant sweep.", "error");
    } finally {
      sweepBtn.disabled = false;
    }
  };

  headerActions.appendChild(sweepBtn);
  header.appendChild(titleGroup);
  header.appendChild(headerActions);

  const body = document.createElement("div");
  body.className = "card-body";

  // User Picker Bar
  const pickerBar = document.createElement("div");
  pickerBar.style.display = "flex";
  pickerBar.style.alignItems = "center";
  pickerBar.style.gap = "16px";
  pickerBar.style.padding = "16px";
  pickerBar.style.backgroundColor = "var(--bg-app)";
  pickerBar.style.borderRadius = "var(--radius-md)";
  pickerBar.style.marginBottom = "24px";
  pickerBar.style.border = "1px solid var(--border-color)";
  pickerBar.style.flexWrap = "wrap";

  const pickerLabel = document.createElement("label");
  pickerLabel.className = "form-label";
  pickerLabel.style.marginBottom = "0";
  pickerLabel.textContent = "Select Persona to Inspect & Manage:";

  const userSelect = document.createElement("select");
  userSelect.className = "form-select";
  userSelect.style.maxWidth = "320px";

  state.users.forEach(u => {
    const opt = document.createElement("option");
    opt.value = u.id;
    opt.textContent = `${u.name} (${u.role_label})`;
    if (u.id === state.currentUser) opt.selected = true;
    userSelect.appendChild(opt);
  });

  pickerBar.appendChild(pickerLabel);
  pickerBar.appendChild(userSelect);
  body.appendChild(pickerBar);

  // Content Area for selected user
  const userContentArea = document.createElement("div");
  body.appendChild(userContentArea);

  card.appendChild(header);
  card.appendChild(body);
  container.appendChild(card);

  userSelect.onchange = () => loadUserAccess(userContentArea, userSelect.value);
  loadUserAccess(userContentArea, userSelect.value);
}

async function loadUserAccess(container, targetUserId) {
  container.innerHTML = '<div class="skeleton" style="height: 140px; margin-bottom: 20px;"></div>';

  try {
    const [summary, grants] = await Promise.all([
      api.get(`/users/${targetUserId}/access`),
      api.get(`/users/${targetUserId}/grants`),
    ]);

    container.innerHTML = "";

    // 1. User Status Banner & Absence Toggle
    const userBanner = document.createElement("div");
    userBanner.style.display = "flex";
    userBanner.style.alignItems = "center";
    userBanner.style.justifyContent = "space-between";
    userBanner.style.padding = "16px";
    userBanner.style.backgroundColor = "var(--bg-surface)";
    userBanner.style.borderRadius = "var(--radius-md)";
    userBanner.style.border = "1px solid var(--border-color)";
    userBanner.style.marginBottom = "20px";
    userBanner.style.flexWrap = "wrap";
    userBanner.style.gap = "12px";

    const bannerLeft = document.createElement("div");
    const h3 = document.createElement("h3");
    h3.style.fontSize = "16px";
    h3.style.fontWeight = "700";
    h3.textContent = `${summary.name} (${summary.user_id})`;

    const sub = document.createElement("div");
    sub.style.fontSize = "13px";
    sub.style.color = "var(--text-muted)";
    sub.textContent = `Type: ${summary.type.toUpperCase()} | Current Status: `;
    sub.appendChild(createUserStatusBadge(summary.status));

    bannerLeft.appendChild(h3);
    bannerLeft.appendChild(sub);

    const bannerRight = document.createElement("div");
    const toggleStatusBtn = document.createElement("button");
    const isCurrentlyAbsent = summary.status === "absent";
    toggleStatusBtn.className = `btn ${isCurrentlyAbsent ? 'btn-success' : 'btn-warning'}`;
    toggleStatusBtn.textContent = isCurrentlyAbsent ? "Mark as Active (Returned)" : "Mark as Absent (Suspend Ops)";
    toggleStatusBtn.onclick = () => handleStatusToggle(summary, container);

    bannerRight.appendChild(toggleStatusBtn);
    userBanner.appendChild(bannerLeft);
    userBanner.appendChild(bannerRight);
    container.appendChild(userBanner);

    // 2. Plain-English Capabilities
    const rulesCard = document.createElement("div");
    rulesCard.style.padding = "16px";
    rulesCard.style.backgroundColor = "var(--bg-app)";
    rulesCard.style.borderRadius = "var(--radius-md)";
    rulesCard.style.border = "1px solid var(--border-color)";
    rulesCard.style.marginBottom = "24px";

    const rulesTitle = document.createElement("h4");
    rulesTitle.style.fontSize = "13px";
    rulesTitle.style.fontWeight = "700";
    rulesTitle.style.textTransform = "uppercase";
    rulesTitle.style.letterSpacing = "0.5px";
    rulesTitle.style.marginBottom = "10px";
    rulesTitle.textContent = "Effective Plain-English Access Rules:";
    rulesCard.appendChild(rulesTitle);

    const ul = document.createElement("ul");
    ul.style.paddingLeft = "20px";
    ul.style.fontSize = "13px";
    ul.style.lineHeight = "1.6";

    if (!summary.plain_english_rules || summary.plain_english_rules.length === 0) {
      const li = document.createElement("li");
      li.style.color = "var(--text-muted)";
      li.textContent = "No active grants assigned (Zero-trust default: all operational actions denied).";
      ul.appendChild(li);
    } else {
      summary.plain_english_rules.forEach(rule => {
        const li = document.createElement("li");
        li.textContent = rule;
        ul.appendChild(li);
      });
    }

    rulesCard.appendChild(ul);
    container.appendChild(rulesCard);

    // 3. Active & Historical Grants Table
    const grantsHeader = document.createElement("div");
    grantsHeader.style.display = "flex";
    grantsHeader.style.alignItems = "center";
    grantsHeader.style.justifyContent = "space-between";
    grantsHeader.style.marginBottom = "12px";

    const grantsTitle = document.createElement("h3");
    grantsTitle.style.fontSize = "15px";
    grantsTitle.style.fontWeight = "700";
    grantsTitle.textContent = `Assigned Grants (${grants.length})`;

    const addGrantBtn = document.createElement("button");
    addGrantBtn.className = "btn btn-primary";
    addGrantBtn.innerHTML = "<span>+</span> Add New Grant";
    addGrantBtn.onclick = () => openAddGrantModal(summary.user_id, container);

    grantsHeader.appendChild(grantsTitle);
    grantsHeader.appendChild(addGrantBtn);
    container.appendChild(grantsHeader);

    const tableWrapper = document.createElement("div");
    tableWrapper.className = "table-container";

    const table = document.createElement("table");
    table.className = "data-table";

    const thead = document.createElement("thead");
    thead.innerHTML = `
      <tr>
        <th>Role</th>
        <th>Scope Specification</th>
        <th>Effect</th>
        <th>Validity Window</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    `;
    table.appendChild(thead);

    const tbody = document.createElement("tbody");

    if (grants.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">
            No grants on record for this user.
          </td>
        </tr>
      `;
    } else {
      grants.forEach(g => {
        const row = document.createElement("tr");

        // Role
        const tdRole = document.createElement("td");
        tdRole.style.fontWeight = "600";
        tdRole.textContent = g.role_id;
        if (g.cover_for_user_id) {
          const coverTag = document.createElement("div");
          coverTag.style.fontSize = "11px";
          coverTag.style.color = "var(--primary)";
          coverTag.textContent = `Cover for: ${g.cover_for_user_id}`;
          tdRole.appendChild(coverTag);
        }

        // Scope
        const tdScope = document.createElement("td");
        tdScope.appendChild(createScopeChip("Client", g.client_id));
        tdScope.appendChild(createScopeChip("Branch", g.branch_id));
        tdScope.appendChild(createScopeChip("Dir", g.direction));
        tdScope.appendChild(createScopeChip("Mode", g.mode));

        // Effect
        const tdEffect = document.createElement("td");
        const effBadge = document.createElement("span");
        effBadge.className = `badge ${g.effect === 'allow' ? 'badge-allow' : 'badge-deny'}`;
        effBadge.textContent = g.effect.toUpperCase();
        tdEffect.appendChild(effBadge);

        // Validity
        const tdValid = document.createElement("td");
        tdValid.style.fontSize = "12px";
        const fromStr = g.valid_from ? new Date(g.valid_from).toLocaleDateString() : "Immediate";
        const toStr = g.valid_to ? new Date(g.valid_to).toLocaleDateString() : "Indefinite";
        tdValid.textContent = `${fromStr} → ${toStr}`;

        // Status
        const tdStatus = document.createElement("td");
        const isRevoked = Boolean(g.revoked_at);
        const statusBadge = document.createElement("span");
        statusBadge.className = `badge ${isRevoked ? 'badge-deny' : 'badge-allow'}`;
        statusBadge.textContent = isRevoked ? "Revoked" : "Active";
        tdStatus.appendChild(statusBadge);

        // Actions
        const tdActions = document.createElement("td");
        if (!isRevoked) {
          const revokeBtn = document.createElement("button");
          revokeBtn.className = "btn btn-danger";
          revokeBtn.style.padding = "3px 8px";
          revokeBtn.style.fontSize = "11px";
          revokeBtn.textContent = "Revoke";
          revokeBtn.onclick = () => handleRevokeGrant(g.id, targetUserId, container);
          tdActions.appendChild(revokeBtn);
        } else {
          tdActions.style.fontSize = "11px";
          tdActions.style.color = "var(--text-muted)";
          tdActions.textContent = `Revoked at ${new Date(g.revoked_at).toLocaleDateString()}`;
        }

        row.appendChild(tdRole);
        row.appendChild(tdScope);
        row.appendChild(tdEffect);
        row.appendChild(tdValid);
        row.appendChild(tdStatus);
        row.appendChild(tdActions);

        tbody.appendChild(row);
      });
    }

    table.appendChild(tbody);
    tableWrapper.appendChild(table);
    container.appendChild(tableWrapper);
  } catch (err) {
    container.innerHTML = `
      <div class="error-state-card" style="border: none;">
        <h3>Unable to load user access</h3>
        <p>${escapeHtml(err.message || 'Error querying user grants.')}</p>
      </div>
    `;
  }
}

function handleStatusToggle(summary, container) {
  const isGoingAbsent = summary.status === "active";
  const newStatus = isGoingAbsent ? "absent" : "active";

  const form = document.createElement("div");
  const p = document.createElement("p");
  p.style.fontSize = "13px";
  p.style.marginBottom = "14px";
  if (isGoingAbsent) {
    p.textContent = `Marking ${summary.name} as ABSENT will immediately suspend their operational actions and auto-unassign their in-flight jobs back to the branch pool.`;
  } else {
    p.textContent = `Marking ${summary.name} as ACTIVE will restore their operational permissions.`;
  }
  form.appendChild(p);

  const group = document.createElement("div");
  group.className = "form-group";
  const lbl = document.createElement("label");
  lbl.className = "form-label";
  lbl.textContent = "Reason for Status Change (Mandatory):";
  const textarea = document.createElement("textarea");
  textarea.className = "form-textarea";
  textarea.placeholder = isGoingAbsent ? "e.g. Medical leave, scheduled PTO..." : "e.g. Returned to active duty...";
  group.appendChild(lbl);
  group.appendChild(textarea);
  form.appendChild(group);

  openModal({
    title: `Change Status: ${summary.name} → ${newStatus.toUpperCase()}`,
    contentElement: form,
    confirmText: `Set to ${newStatus.toUpperCase()}`,
    confirmClass: isGoingAbsent ? "btn-warning" : "btn-success",
    onConfirm: async () => {
      const reason = textarea.value.trim();
      if (reason.length < 3) {
        showToast("A valid reason is required.", "warning");
        return false;
      }

      try {
        await api.patch(`/users/${summary.user_id}/status`, { status: newStatus, reason });
        showToast(`User ${summary.name} status updated to ${newStatus}.`, "success");
        loadUserAccess(container, summary.user_id);
        return true;
      } catch (err) {
        showToast(err.message || "Failed to update user status.", "error");
        return false;
      }
    },
  });
}

function handleRevokeGrant(grantId, userId, container) {
  const form = document.createElement("div");
  const p = document.createElement("p");
  p.style.fontSize = "13px";
  p.style.marginBottom = "14px";
  p.textContent = `Revoking grant ${grantId} will immediately remove these permissions and return in-flight assigned jobs to the pool.`;
  form.appendChild(p);

  const group = document.createElement("div");
  group.className = "form-group";
  const lbl = document.createElement("label");
  lbl.className = "form-label";
  lbl.textContent = "Revocation Reason (Mandatory):";
  const textarea = document.createElement("textarea");
  textarea.className = "form-textarea";
  textarea.placeholder = "e.g. Transferred to another branch, reassignment...";
  group.appendChild(lbl);
  group.appendChild(textarea);
  form.appendChild(group);

  openModal({
    title: `Revoke Grant: ${grantId}`,
    contentElement: form,
    confirmText: "Revoke Grant",
    confirmClass: "btn-danger",
    onConfirm: async () => {
      const reason = textarea.value.trim();
      if (reason.length < 3) {
        showToast("A revocation reason is required.", "warning");
        return false;
      }

      try {
        await api.post(`/grants/${grantId}/revoke`, { reason });
        showToast(`Grant ${grantId} was successfully revoked.`, "success");
        loadUserAccess(container, userId);
        return true;
      } catch (err) {
        showToast(err.message || "Failed to revoke grant.", "error");
        return false;
      }
    },
  });
}

function openAddGrantModal(userId, container) {
  const form = document.createElement("div");

  form.innerHTML = `
    <div class="form-group">
      <label class="form-label">Role:</label>
      <select id="new-grant-role" class="form-select">
        <option value="maker">Maker (Checklist Preparer)</option>
        <option value="checker">Checker (Quality & Verification)</option>
        <option value="filer">Filer (Customs Declaration)</option>
        <option value="supervisor">Supervisor (Operations Reassignment)</option>
        <option value="ops_admin">Ops Admin (Operational Overrides)</option>
        <option value="access_admin">Access Admin (Grant Management)</option>
        <option value="viewer">Viewer (Read-only)</option>
      </select>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
      <div class="form-group">
        <label class="form-label">Client Scope (optional):</label>
        <input type="text" id="new-grant-client" class="form-input" placeholder="ALL (or e.g. C01, C02)">
      </div>
      <div class="form-group">
        <label class="form-label">Branch Scope (optional):</label>
        <input type="text" id="new-grant-branch" class="form-input" placeholder="ALL (or e.g. BR-MUM, BR-DEL)">
      </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
      <div class="form-group">
        <label class="form-label">Direction:</label>
        <select id="new-grant-dir" class="form-select">
          <option value="">ALL Directions</option>
          <option value="IMPORT">IMPORT</option>
          <option value="EXPORT">EXPORT</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Mode:</label>
        <select id="new-grant-mode" class="form-select">
          <option value="">ALL Modes</option>
          <option value="AIR">AIR</option>
          <option value="FCL">FCL</option>
          <option value="LCL">LCL</option>
        </select>
      </div>
    </div>

    <div class="form-group">
      <label class="form-label">Effect:</label>
      <select id="new-grant-effect" class="form-select">
        <option value="allow" selected>ALLOW (Permit action within scope)</option>
        <option value="deny">DENY (Explicit Recusal / Block)</option>
      </select>
    </div>

    <div class="form-group">
      <label class="form-label">Administrative Reason (Mandatory):</label>
      <textarea id="new-grant-reason" class="form-textarea" placeholder="Justification for granting this role scope..."></textarea>
    </div>
  `;

  openModal({
    title: `Add Grant for ${userId}`,
    contentElement: form,
    confirmText: "Create Grant",
    confirmClass: "btn-primary",
    onConfirm: async () => {
      const roleId = document.getElementById("new-grant-role").value;
      const clientId = document.getElementById("new-grant-client").value.trim() || null;
      const branchId = document.getElementById("new-grant-branch").value.trim() || null;
      const direction = document.getElementById("new-grant-dir").value || null;
      const mode = document.getElementById("new-grant-mode").value || null;
      const effect = document.getElementById("new-grant-effect").value;
      const reason = document.getElementById("new-grant-reason").value.trim();

      if (reason.length < 3) {
        showToast("A valid administrative reason is required.", "warning");
        return false;
      }

      try {
        await api.post("/grants", {
          user_id: userId,
          grants: [
            {
              role_id: roleId,
              client_id: clientId,
              branch_id: branchId,
              direction,
              mode,
              effect,
              reason,
            },
          ],
        });
        showToast("New grant successfully created and activated.", "success");
        loadUserAccess(container, userId);
        return true;
      } catch (err) {
        showToast(err.message || "Failed to create grant.", "error");
        return false;
      }
    },
  });
}
