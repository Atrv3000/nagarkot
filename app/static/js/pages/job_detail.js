/**
 * Nagarkot Access Control Service - Job Detail Page Component
 * Displays shipment lifecycle stepper, key dimensions, pre-evaluated decision action buttons,
 * execution modals with reason/assignee inputs, audit history, and who-could analysis.
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { router } from "../router.js";
import { createStageBadge, createOutcomeBadge } from "../components/badge.js";
import { createJobStepper } from "../components/stepper.js";
import { openModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import {
  ACTION_CONFIG,
  getFriendlyReason,
  formatFullDateTime,
  formatRelativeTime
} from "../labels.js";

const ALL_ACTIONS = [
  "prepare",
  "check",
  "file",
  "cancel",
  "cancel_filed",
  "reopen",
  "reassign",
  "override_send_back",
];

export async function renderJobDetailPage(container, params) {
  const jobId = params.id;
  document.getElementById("view-heading").textContent = `Shipment ${jobId}`;
  container.innerHTML = `
    <div class="card">
      <div class="card-body">
        <div class="skeleton" style="width: 50%; height: 24px; margin-bottom: 16px;"></div>
        <div class="skeleton" style="width: 100%; height: 120px; margin-bottom: 24px;"></div>
        <div class="skeleton" style="width: 80%; height: 160px;"></div>
      </div>
    </div>
  `;

  try {
    const job = await api.get(`/jobs/${jobId}`);
    renderJobView(container, job);
  } catch (err) {
    container.innerHTML = "";
    const card = document.createElement("div");
    card.className = "card";
    const body = document.createElement("div");
    body.className = "card-body";
    const errCard = document.createElement("div");
    errCard.className = "error-state-card";
    errCard.style.border = "none";
    const h3 = document.createElement("h3");
    h3.textContent = `Unable to access shipment ${jobId}`;
    const p = document.createElement("p");
    p.textContent = err.message || "Job not found or not visible within your scope.";
    const link = document.createElement("a");
    link.href = "#/queue";
    link.className = "btn btn-primary";
    link.textContent = "Return to My Queue";

    errCard.appendChild(h3);
    errCard.appendChild(p);
    errCard.appendChild(link);
    body.appendChild(errCard);
    card.appendChild(body);
    container.appendChild(card);
  }
}

function renderJobView(container, job) {
  container.innerHTML = "";

  // Main Card
  const card = document.createElement("div");
  card.className = "card";

  // Card Header: Ref, ID, Badge, and Action Buttons
  const header = document.createElement("div");
  header.className = "card-header";

  const headerLeft = document.createElement("div");
  headerLeft.style.display = "flex";
  headerLeft.style.alignItems = "center";
  headerLeft.style.gap = "12px";

  const backBtn = document.createElement("a");
  backBtn.href = "#/queue";
  backBtn.className = "btn btn-secondary";
  backBtn.textContent = "← Back";

  const titleGroup = document.createElement("div");
  const title = document.createElement("h2");
  title.className = "card-title";
  title.textContent = job.ref;

  const sub = document.createElement("div");
  sub.className = "card-subtitle";
  sub.textContent = `ID: ${job.id} | Cycle: ${job.cycle || 1}`;

  titleGroup.appendChild(title);
  titleGroup.appendChild(sub);

  headerLeft.appendChild(backBtn);
  headerLeft.appendChild(titleGroup);
  headerLeft.appendChild(createStageBadge(job.stage));

  const headerRight = document.createElement("div");
  headerRight.style.display = "flex";
  headerRight.style.gap = "10px";

  const explainBtn = document.createElement("a");
  explainBtn.href = `#/explain?job_id=${encodeURIComponent(job.id)}`;
  explainBtn.className = "btn btn-secondary";
  explainBtn.innerHTML = "<span>🔍</span> Inspect Decision Engine";

  headerRight.appendChild(explainBtn);
  header.appendChild(headerLeft);
  header.appendChild(headerRight);

  // Card Body
  const body = document.createElement("div");
  body.className = "card-body";

  // 1. Horizontal Stepper
  const stepper = createJobStepper(job);
  body.appendChild(stepper);

  // 2. Shipment Dimensions Grid
  const gridTitle = document.createElement("h3");
  gridTitle.style.fontSize = "14px";
  gridTitle.style.fontWeight = "700";
  gridTitle.style.marginBottom = "12px";
  gridTitle.textContent = "Shipment Overview & Handlers";
  body.appendChild(gridTitle);

  const grid = document.createElement("div");
  grid.className = "field-grid";

  const fields = [
    { label: "Client ID", value: job.client_id },
    { label: "Branch", value: job.branch_id },
    { label: "Direction", value: job.direction },
    { label: "Transport Mode", value: job.mode },
    { label: "Assigned Handler", value: job.assigned_to || (state.currentUserObj?.type === "client" ? "— (Redacted)" : "Unassigned (Branch Pool)") },
    { label: "Prepared By", value: job.prepared_by || "—" },
    { label: "Checked By", value: job.checked_by || "—" },
    { label: "Filed By", value: job.filed_by || "—" },
    { label: "Created At", value: formatRelativeTime(job.created_at) },
    { label: "Last Updated", value: formatRelativeTime(job.updated_at) },
  ];

  fields.forEach(f => {
    const item = document.createElement("div");
    item.className = "field-item";
    const lbl = document.createElement("span");
    lbl.className = "field-label";
    lbl.textContent = f.label;
    const val = document.createElement("span");
    val.className = "field-value";
    val.textContent = f.value;
    item.appendChild(lbl);
    item.appendChild(val);
    grid.appendChild(item);
  });

  body.appendChild(grid);

  if (job.internal_notes) {
    const notesBox = document.createElement("div");
    notesBox.style.padding = "10px 14px";
    notesBox.style.backgroundColor = "var(--bg-app)";
    notesBox.style.borderRadius = "var(--radius-md)";
    notesBox.style.marginBottom = "20px";
    notesBox.style.fontSize = "12px";
    notesBox.style.border = "1px solid var(--border-color)";
    notesBox.textContent = `Internal Operations Note: ${job.internal_notes}`;
    body.appendChild(notesBox);
  }

  // 3. Actions Panel
  const actionsSection = document.createElement("div");
  actionsSection.style.marginTop = "24px";
  actionsSection.style.paddingTop = "20px";
  actionsSection.style.borderTop = "1px solid var(--border-color)";

  const actionsHeader = document.createElement("div");
  actionsHeader.style.display = "flex";
  actionsHeader.style.alignItems = "center";
  actionsHeader.style.justifyContent = "space-between";
  actionsHeader.style.marginBottom = "8px";

  const actionsTitle = document.createElement("h3");
  actionsTitle.style.fontSize = "15px";
  actionsTitle.style.fontWeight = "700";
  actionsTitle.textContent = "Available Actions for Current Persona";

  const actionsHint = document.createElement("span");
  actionsHint.style.fontSize = "12px";
  actionsHint.style.color = "var(--text-muted)";
  actionsHint.textContent = `Evaluated in real-time as ${state.currentUserObj?.name || state.currentUser}`;

  actionsHeader.appendChild(actionsTitle);
  actionsHeader.appendChild(actionsHint);
  actionsSection.appendChild(actionsHeader);

  const actionsGrid = document.createElement("div");
  actionsGrid.className = "actions-grid";
  actionsSection.appendChild(actionsGrid);
  body.appendChild(actionsSection);

  // Evaluate all actions asynchronously via /decide
  evaluateAllActions(actionsGrid, job);

  // 4. Tabs Section (History & Who-Could)
  const tabsContainer = document.createElement("div");
  tabsContainer.style.marginTop = "32px";
  tabsContainer.style.paddingTop = "24px";
  tabsContainer.style.borderTop = "1px solid var(--border-color)";

  const tabNav = document.createElement("div");
  tabNav.className = "tab-nav";

  const tabBtnHistory = document.createElement("button");
  tabBtnHistory.className = "tab-btn tab-active";
  tabBtnHistory.textContent = "📜 Audit History";

  const tabBtnWhoCould = document.createElement("button");
  tabBtnWhoCould.className = "tab-btn";
  tabBtnWhoCould.textContent = "👥 Who Could Do This?";

  tabNav.appendChild(tabBtnHistory);
  tabNav.appendChild(tabBtnWhoCould);

  const historyContent = document.createElement("div");
  historyContent.className = "tab-content tab-content-active";

  const whoCouldContent = document.createElement("div");
  whoCouldContent.className = "tab-content";

  tabBtnHistory.onclick = () => {
    tabBtnHistory.classList.add("tab-active");
    tabBtnWhoCould.classList.remove("tab-active");
    historyContent.classList.add("tab-content-active");
    whoCouldContent.classList.remove("tab-content-active");
  };

  tabBtnWhoCould.onclick = () => {
    tabBtnWhoCould.classList.add("tab-active");
    tabBtnHistory.classList.remove("tab-active");
    whoCouldContent.classList.add("tab-content-active");
    historyContent.classList.remove("tab-content-active");
    if (!whoCouldContent.dataset.loaded) {
      loadWhoCouldTab(whoCouldContent, job);
    }
  };

  tabsContainer.appendChild(tabNav);
  tabsContainer.appendChild(historyContent);
  tabsContainer.appendChild(whoCouldContent);
  body.appendChild(tabsContainer);

  card.appendChild(header);
  card.appendChild(body);
  container.appendChild(card);

  // Load history tab content
  loadHistoryTab(historyContent, job.id);
}

/**
 * Pre-evaluates all 8 engine actions via /decide and builds interactive cards.
 */
async function evaluateAllActions(grid, job) {
  grid.innerHTML = '<div class="skeleton" style="grid-column: 1 / -1; height: 100px;"></div>';

  try {
    const promises = ALL_ACTIONS.map(action =>
      api.get("/decide", {
        user_id: state.currentUser,
        action,
        job_id: job.id,
      }).then(dec => ({ action, dec })).catch(() => ({ action, dec: null }))
    );

    const results = await Promise.all(promises);
    grid.innerHTML = "";

    results.forEach(({ action, dec }) => {
      const meta = ACTION_CONFIG[action] || { label: action, badgeClass: "btn-secondary" };
      const card = document.createElement("div");

      const isAllowed = dec?.allowed === true;
      const isNeedsApproval = dec?.outcome === "NEEDS_APPROVAL";
      const isActionable = isAllowed || isNeedsApproval;

      card.className = `action-card ${!isActionable ? 'action-card-disabled' : ''}`;

      const cardHead = document.createElement("div");
      cardHead.className = "action-card-header";

      const title = document.createElement("div");
      title.className = "action-title";
      title.textContent = meta.label;

      const badge = createOutcomeBadge(dec?.outcome || "DENY");
      cardHead.appendChild(title);
      cardHead.appendChild(badge);
      card.appendChild(cardHead);

      const reason = document.createElement("div");
      reason.className = "action-reason-text";

      if (isAllowed) {
        reason.className += " action-reason-allowed";
        reason.textContent = "Permitted under active grants and four-eyes policy.";
      } else if (isNeedsApproval) {
        reason.className += " action-reason-allowed";
        reason.textContent = "Action requires formal two-person Compliance Approval.";
      } else {
        reason.className += " action-reason-denied";
        const friendly = getFriendlyReason(dec?.primary_reason);
        reason.textContent = friendly;
      }
      card.appendChild(reason);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `btn ${isActionable ? (isNeedsApproval ? 'btn-warning' : 'btn-primary') : 'btn-secondary'}`;
      btn.textContent = isNeedsApproval ? "Request Approval" : "Execute Action";
      btn.disabled = !isActionable;

      if (isActionable) {
        btn.onclick = () => handleActionClick(action, job, dec);
      }

      card.appendChild(btn);
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = "";
    const errCard = document.createElement("div");
    errCard.className = "error-state-card";
    errCard.style.gridColumn = "1 / -1";
    errCard.textContent = `Failed to evaluate actions: ${err.message || 'error'}`;
    grid.appendChild(errCard);
  }
}

/**
 * Handles action execution modal with reason / assignee input.
 */
function handleActionClick(action, job, decision) {
  const meta = ACTION_CONFIG[action] || { label: action };
  const requiresReason = ["cancel", "cancel_filed", "reopen", "override_send_back"].includes(action);
  const isReassign = action === "reassign";
  const isNeedsApproval = decision.outcome === "NEEDS_APPROVAL";

  const formContent = document.createElement("div");

  const desc = document.createElement("p");
  desc.style.fontSize = "13px";
  desc.style.marginBottom = "14px";
  desc.style.color = "var(--text-secondary)";

  if (isNeedsApproval) {
    desc.textContent = `Submitting '${meta.label}' on shipment ${job.ref} will initiate a two-person compliance approval workflow for an authorized Approver (e.g. Sunita Patil).`;
  } else {
    desc.textContent = `You are about to execute '${meta.label}' on shipment ${job.ref}.`;
  }
  formContent.appendChild(desc);

  let assigneeSelect = null;
  if (isReassign) {
    const groupAssign = document.createElement("div");
    groupAssign.className = "form-group";
    const lbl = document.createElement("label");
    lbl.className = "form-label";
    lbl.textContent = "New Assigned Staff Member:";
    assigneeSelect = document.createElement("select");
    assigneeSelect.className = "form-select";

    state.users.filter(u => u.type === "staff").forEach(u => {
      const opt = document.createElement("option");
      opt.value = u.id;
      opt.textContent = `${u.name} (${u.role_label})`;
      if (u.id === job.assigned_to) opt.selected = true;
      assigneeSelect.appendChild(opt);
    });

    groupAssign.appendChild(lbl);
    groupAssign.appendChild(assigneeSelect);
    formContent.appendChild(groupAssign);
  }

  const groupReason = document.createElement("div");
  groupReason.className = "form-group";
  const lblReason = document.createElement("label");
  lblReason.className = "form-label";
  lblReason.textContent = requiresReason ? "Justification (Mandatory):" : "Reason / Operational Notes (Optional):";

  const textareaReason = document.createElement("textarea");
  textareaReason.className = "form-textarea";
  textareaReason.placeholder = requiresReason ? "Explain reason for this override or modification..." : "Optional notes for audit log...";
  groupReason.appendChild(lblReason);
  groupReason.appendChild(textareaReason);
  formContent.appendChild(groupReason);

  openModal({
    title: `${meta.label} - ${job.ref}`,
    contentElement: formContent,
    confirmText: isNeedsApproval ? "Submit for Approval" : "Execute Action",
    confirmClass: isNeedsApproval ? "btn-warning" : "btn-primary",
    onConfirm: async () => {
      const reasonVal = textareaReason.value.trim();
      if (requiresReason && reasonVal.length < 3) {
        showToast("A valid written justification (minimum 3 characters) is required.", "warning");
        return false;
      }

      const body = {};
      if (reasonVal) body.reason = reasonVal;
      if (isReassign && assigneeSelect) body.new_assignee_id = assigneeSelect.value;

      try {
        const resp = await api.post(`/jobs/${job.id}/actions/${action}`, body);

        if (resp && resp.status === "NEEDS_APPROVAL") {
          showToast(`Submitted for approval! Approval ID: ${resp.approval_id}`, "warning", 6000);
        } else {
          showToast(`Success: Action '${meta.label}' executed. Stage is now ${resp?.stage || 'updated'}.`, "success");
        }

        // Re-render Job Detail with fresh data
        renderJobDetailPage(document.getElementById("main-content"), { id: job.id });
        return true;
      } catch (err) {
        showToast(err.message || "Failed to execute action.", "error");
        return false;
      }
    },
  });
}

/**
 * Loads audit history timeline.
 */
async function loadHistoryTab(container, jobId) {
  container.innerHTML = '<div class="skeleton" style="height: 100px;"></div>';

  try {
    const events = await api.get(`/jobs/${jobId}/history`);
    container.innerHTML = "";

    if (!events || events.length === 0) {
      container.innerHTML = '<p style="color: var(--text-muted); padding: 16px 0;">No history events recorded yet.</p>';
      return;
    }

    const timeline = document.createElement("div");
    timeline.className = "timeline";

    events.forEach(evt => {
      const item = document.createElement("div");
      item.className = "timeline-item";

      const dot = document.createElement("div");
      dot.className = "timeline-dot";

      const header = document.createElement("div");
      header.className = "timeline-item-header";

      const title = document.createElement("div");
      title.className = "timeline-event-name";
      title.textContent = `${evt.event_type} (${evt.action || 'system'}) by ${evt.actor_id}`;

      const time = document.createElement("div");
      time.className = "timeline-event-time";
      time.textContent = formatFullDateTime(evt.at);

      header.appendChild(title);
      header.appendChild(time);

      const body = document.createElement("div");
      body.className = "timeline-event-body";

      let detailParts = [];
      if (evt.decision) detailParts.push(`Decision: ${evt.decision}`);
      if (evt.is_override) detailParts.push("⚠️ Administrative Override");
      if (evt.reason_codes && evt.reason_codes.length > 0) detailParts.push(`Reason codes: ${evt.reason_codes.join(', ')}`);
      if (evt.after_state?.stage) detailParts.push(`New Stage: ${evt.after_state.stage}`);
      if (evt.after_state?.reason) detailParts.push(`Note: "${evt.after_state.reason}"`);

      body.textContent = detailParts.join(" | ") || "Event logged to audit database.";

      item.appendChild(dot);
      item.appendChild(header);
      item.appendChild(body);
      timeline.appendChild(item);
    });

    container.appendChild(timeline);
  } catch (err) {
    container.innerHTML = "";
    const errCard = document.createElement("div");
    errCard.className = "error-state-card";
    errCard.style.border = "none";
    errCard.textContent = `Unable to load job history: ${err.message || 'error'}`;
    container.appendChild(errCard);
  }
}

/**
 * Loads "Who Could Do This?" audit analysis tab.
 */
async function loadWhoCouldTab(container, job) {
  container.dataset.loaded = "true";
  container.innerHTML = "";

  const controls = document.createElement("div");
  controls.style.display = "flex";
  controls.style.alignItems = "center";
  controls.style.gap = "12px";
  controls.style.marginBottom = "20px";
  controls.style.flexWrap = "wrap";

  const actionSelect = document.createElement("select");
  actionSelect.className = "form-select";
  actionSelect.style.maxWidth = "200px";

  ["prepare", "check", "file", "cancel", "cancel_filed", "reopen", "override_send_back"].forEach(act => {
    const opt = document.createElement("option");
    opt.value = act;
    opt.textContent = `Action: ${act}`;
    actionSelect.appendChild(opt);
  });

  const analyzeBtn = document.createElement("button");
  analyzeBtn.className = "btn btn-primary";
  analyzeBtn.textContent = "Analyze Eligible Actors";

  controls.appendChild(actionSelect);
  controls.appendChild(analyzeBtn);
  container.appendChild(controls);

  const resultsArea = document.createElement("div");
  container.appendChild(resultsArea);

  const runAnalysis = async () => {
    resultsArea.innerHTML = '<div class="skeleton" style="height: 120px;"></div>';
    const chosenAction = actionSelect.value;

    try {
      const data = await api.get(`/jobs/${job.id}/who-could`, { action: chosenAction });
      resultsArea.innerHTML = "";

      const summaryCard = document.createElement("div");
      summaryCard.style.padding = "14px";
      summaryCard.style.backgroundColor = "var(--bg-app)";
      summaryCard.style.borderRadius = "var(--radius-md)";
      summaryCard.style.marginBottom = "16px";
      summaryCard.style.fontSize = "13px";

      const h4 = document.createElement("div");
      h4.style.fontWeight = "700";
      h4.style.marginBottom = "4px";
      h4.textContent = `Evaluation for action '${chosenAction}' at evaluated stage ${data.job_stage_at_timestamp}:`;

      const p = document.createElement("div");
      p.textContent = `${data.who_could_have_performed.length} user(s) held valid authorization.`;
      if (data.actual_actor) {
        p.textContent += ` Actual historical actor recorded in audit: ${data.actual_actor}`;
      }

      summaryCard.appendChild(h4);
      summaryCard.appendChild(p);
      resultsArea.appendChild(summaryCard);

      if (data.who_could_have_performed.length > 0) {
        const table = document.createElement("table");
        table.className = "data-table";
        const thead = document.createElement("thead");
        thead.innerHTML = "<tr><th>Eligible User</th><th>Matched Grants</th></tr>";
        const tbody = document.createElement("tbody");

        data.who_could_have_performed.forEach(u => {
          const tr = document.createElement("tr");
          const tdUser = document.createElement("td");
          const strong = document.createElement("strong");
          strong.textContent = u.user_id;
          tdUser.appendChild(strong);

          const tdGrants = document.createElement("td");
          tdGrants.textContent = u.matched_grants.join(", ") || "Direct grant";

          tr.appendChild(tdUser);
          tr.appendChild(tdGrants);
          tbody.appendChild(tr);
        });

        table.appendChild(thead);
        table.appendChild(tbody);
        resultsArea.appendChild(table);
      } else {
        const noOne = document.createElement("p");
        noOne.style.color = "var(--text-muted)";
        noOne.textContent = "No users were authorized to perform this action at the evaluated timestamp.";
        resultsArea.appendChild(noOne);
      }
    } catch (err) {
      resultsArea.innerHTML = "";
      const errCard = document.createElement("div");
      errCard.className = "empty-state-card";
      errCard.style.border = "none";
      const h3 = document.createElement("h3");
      h3.textContent = "Audit Analysis Unavailable";
      const p = document.createElement("p");
      p.textContent = err.message || "Who-could analysis requires access.manage or audit.view permission.";
      errCard.appendChild(h3);
      errCard.appendChild(p);
      resultsArea.appendChild(errCard);
    }
  };
    }
  };

  analyzeBtn.onclick = runAnalysis;
  // Trigger initial run
  runAnalysis();
}
