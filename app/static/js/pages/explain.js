/**
 * Nagarkot Access Control Service - Explain & Compare View
 * Answers "Why can/can't this user act?" and "Why can she do this and he can't?"
 * Includes 8-stage checklist breakdown, primary failing check highlight, and historical time-travel.
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { createDecisionChecklist } from "../components/checklist.js";

const POPULAR_SHOWCASE_JOBS = [
  { id: "JOB-SHOWCASE-01", label: "JOB-SHOWCASE-01 (FILED - Two-Person Rule)" },
  { id: "JOB-SHOWCASE-02", label: "JOB-SHOWCASE-02 (PREPARED - SoD Conflict for Asha)" },
  { id: "JOB-SHOWCASE-03", label: "JOB-SHOWCASE-03 (PREPARED - Stuck Job Imran/Meera)" },
  { id: "JOB-SHOWCASE-05", label: "JOB-SHOWCASE-05 (PREPARED - Rohit Mumbai Import Check)" },
  { id: "JOB-SHOWCASE-06", label: "JOB-SHOWCASE-06 (PREPARED - Rohit Export Deny)" },
  { id: "JOB-SHOWCASE-07", label: "JOB-SHOWCASE-07 (PREPARED - Rohit Other Branch Deny)" },
  { id: "JOB-SHOWCASE-08", label: "JOB-SHOWCASE-08 (CONFIRMED - Delhi Cover for Pooja)" },
  { id: "JOB-HIST-DEMO-01", label: "JOB-HIST-DEMO-01 (FILED - Historical Replay Oct 3)" },
];

export async function renderExplainPage(container) {
  document.getElementById("view-heading").textContent = "Decision Explainer & Parity Comparator";
  container.innerHTML = "";

  // Parse hash query params if any (e.g. #/explain?job_id=JOB-SHOWCASE-05)
  const hash = window.location.hash;
  const qIdx = hash.indexOf("?");
  const searchParams = new URLSearchParams(qIdx !== -1 ? hash.slice(qIdx + 1) : "");
  const defaultJobId = searchParams.get("job_id") || "JOB-SHOWCASE-05";
  const defaultAction = searchParams.get("action") || "check";

  const card = document.createElement("div");
  card.className = "card";

  const header = document.createElement("div");
  header.className = "card-header";

  const titleGroup = document.createElement("div");
  const title = document.createElement("h2");
  title.className = "card-title";
  title.textContent = "Decision Inspector & Four-Eyes Explainer";

  const sub = document.createElement("div");
  sub.className = "card-subtitle";
  sub.textContent = "Transparent 8-stage decision pipeline verification and parity comparison";

  titleGroup.appendChild(title);
  titleGroup.appendChild(sub);
  header.appendChild(titleGroup);

  const body = document.createElement("div");
  body.className = "card-body";

  // Tab switcher: Single Inspector vs Compare View
  const modeNav = document.createElement("div");
  modeNav.className = "tab-nav";

  const tabSingle = document.createElement("button");
  tabSingle.className = "tab-btn tab-active";
  tabSingle.textContent = "🔍 Single User Decision Trace";

  const tabCompare = document.createElement("button");
  tabCompare.className = "tab-btn";
  tabCompare.textContent = "⚖️ Side-by-Side Comparator";

  modeNav.appendChild(tabSingle);
  modeNav.appendChild(tabCompare);
  body.appendChild(modeNav);

  // Container for modes
  const singleContainer = document.createElement("div");
  const compareContainer = document.createElement("div");
  compareContainer.style.display = "none";

  tabSingle.onclick = () => {
    tabSingle.classList.add("tab-active");
    tabCompare.classList.remove("tab-active");
    singleContainer.style.display = "block";
    compareContainer.style.display = "none";
  };

  tabCompare.onclick = () => {
    tabCompare.classList.add("tab-active");
    tabSingle.classList.remove("tab-active");
    compareContainer.style.display = "block";
    singleContainer.style.display = "none";
  };

  body.appendChild(singleContainer);
  body.appendChild(compareContainer);

  card.appendChild(header);
  card.appendChild(body);
  container.appendChild(card);

  // Setup views
  setupSingleInspector(singleContainer, defaultJobId, defaultAction);
  setupCompareView(compareContainer, defaultJobId, defaultAction);
}

function setupSingleInspector(container, initialJobId, initialAction) {
  const form = document.createElement("div");
  form.style.display = "grid";
  form.style.gridTemplateColumns = "repeat(auto-fit, minmax(200px, 1fr))";
  form.style.gap = "14px";
  form.style.marginBottom = "24px";
  form.style.padding = "16px";
  form.style.backgroundColor = "var(--bg-app)";
  form.style.borderRadius = "var(--radius-md)";
  form.style.border = "1px solid var(--border-color)";

  // User select
  const userGroup = document.createElement("div");
  userGroup.className = "form-group";
  userGroup.style.marginBottom = "0";
  const userLabel = document.createElement("label");
  userLabel.className = "form-label";
  userLabel.textContent = "Evaluating Persona:";
  const userSelect = document.createElement("select");
  userSelect.className = "form-select";

  state.users.forEach(u => {
    const opt = document.createElement("option");
    opt.value = u.id;
    opt.textContent = `${u.name} (${u.role_label})`;
    if (u.id === state.currentUser) opt.selected = true;
    userSelect.appendChild(opt);
  });
  userGroup.appendChild(userLabel);
  userGroup.appendChild(userSelect);

  // Action select
  const actionGroup = document.createElement("div");
  actionGroup.className = "form-group";
  actionGroup.style.marginBottom = "0";
  const actionLabel = document.createElement("label");
  actionLabel.className = "form-label";
  actionLabel.textContent = "Attempted Action:";
  const actionSelect = document.createElement("select");
  actionSelect.className = "form-select";
  ["prepare", "check", "file", "cancel", "cancel_filed", "reopen", "reassign", "override_send_back", "view"].forEach(a => {
    const opt = document.createElement("option");
    opt.value = a;
    opt.textContent = a;
    if (a === initialAction) opt.selected = true;
    actionSelect.appendChild(opt);
  });
  actionGroup.appendChild(actionLabel);
  actionGroup.appendChild(actionSelect);

  // Job ID input / select
  const jobGroup = document.createElement("div");
  jobGroup.className = "form-group";
  jobGroup.style.marginBottom = "0";
  const jobLabel = document.createElement("label");
  jobLabel.className = "form-label";
  jobLabel.textContent = "Target Shipment ID:";
  const jobInput = document.createElement("input");
  jobInput.className = "form-input";
  jobInput.value = initialJobId;
  jobInput.setAttribute("list", "showcase-jobs-list");

  const datalist = document.createElement("datalist");
  datalist.id = "showcase-jobs-list";
  POPULAR_SHOWCASE_JOBS.forEach(j => {
    const opt = document.createElement("option");
    opt.value = j.id;
    opt.textContent = j.label;
    datalist.appendChild(opt);
  });

  jobGroup.appendChild(jobLabel);
  jobGroup.appendChild(jobInput);
  jobGroup.appendChild(datalist);

  // Historical As-Of
  const asOfGroup = document.createElement("div");
  asOfGroup.className = "form-group";
  asOfGroup.style.marginBottom = "0";
  const asOfLabel = document.createElement("label");
  asOfLabel.className = "form-label";
  asOfLabel.textContent = "Time-Travel 'As Of' (Optional):";
  const asOfInput = document.createElement("input");
  asOfInput.type = "text";
  asOfInput.className = "form-input";
  asOfInput.placeholder = "e.g. 2026-10-03T14:00:00Z";
  asOfGroup.appendChild(asOfLabel);
  asOfGroup.appendChild(asOfInput);

  form.appendChild(userGroup);
  form.appendChild(actionGroup);
  form.appendChild(jobGroup);
  form.appendChild(asOfGroup);

  const btnContainer = document.createElement("div");
  btnContainer.style.gridColumn = "1 / -1";
  btnContainer.style.display = "flex";
  btnContainer.style.justifyContent = "flex-end";
  const inspectBtn = document.createElement("button");
  inspectBtn.className = "btn btn-primary";
  inspectBtn.textContent = "Run Decision Pipeline";
  btnContainer.appendChild(inspectBtn);
  form.appendChild(btnContainer);

  container.appendChild(form);

  const resultArea = document.createElement("div");
  container.appendChild(resultArea);

  const executeInspect = async () => {
    resultArea.innerHTML = '<div class="skeleton" style="height: 180px;"></div>';
    const params = {
      user_id: userSelect.value,
      action: actionSelect.value,
      job_id: jobInput.value.trim(),
    };
    if (asOfInput.value.trim()) {
      params.at = asOfInput.value.trim();
    }

    try {
      const decision = await api.get("/decide", params);
      resultArea.innerHTML = "";

      // Render 8-stage checklist
      const checklist = createDecisionChecklist(decision);
      resultArea.appendChild(checklist);

      // Raw JSON Collapsible
      const details = document.createElement("details");
      details.style.marginTop = "20px";
      details.style.fontSize = "12px";
      const summary = document.createElement("summary");
      summary.style.cursor = "pointer";
      summary.style.color = "var(--text-muted)";
      summary.textContent = "Show Raw Decision Response JSON";
      const pre = document.createElement("pre");
      pre.style.marginTop = "8px";
      pre.style.padding = "12px";
      pre.style.backgroundColor = "var(--bg-app)";
      pre.style.borderRadius = "var(--radius-sm)";
      pre.style.overflowX = "auto";
      pre.textContent = JSON.stringify(decision, null, 2);

      details.appendChild(summary);
      details.appendChild(pre);
      resultArea.appendChild(details);
    } catch (err) {
      resultArea.innerHTML = `
        <div class="error-state-card" style="border: none;">
          <h3>Pipeline Evaluation Failed</h3>
          <p>${err.message || 'Unable to execute decision evaluation.'}</p>
        </div>
      `;
    }
  };

  inspectBtn.onclick = executeInspect;
  // Run on initial render
  executeInspect();
}

function setupCompareView(container, initialJobId, initialAction) {
  const form = document.createElement("div");
  form.style.display = "grid";
  form.style.gridTemplateColumns = "repeat(auto-fit, minmax(200px, 1fr))";
  form.style.gap = "14px";
  form.style.marginBottom = "24px";
  form.style.padding = "16px";
  form.style.backgroundColor = "var(--bg-app)";
  form.style.borderRadius = "var(--radius-md)";
  form.style.border = "1px solid var(--border-color)";

  // User A (Default: Priya Nair)
  const userAGroup = document.createElement("div");
  userAGroup.className = "form-group";
  userAGroup.style.marginBottom = "0";
  const userALabel = document.createElement("label");
  userALabel.className = "form-label";
  userALabel.textContent = "User A (Primary Persona):";
  const userASelect = document.createElement("select");
  userASelect.className = "form-select";
  state.users.forEach(u => {
    const opt = document.createElement("option");
    opt.value = u.id;
    opt.textContent = `${u.name} (${u.role_label})`;
    if (u.id === "priya-nair") opt.selected = true;
    userASelect.appendChild(opt);
  });
  userAGroup.appendChild(userALabel);
  userAGroup.appendChild(userASelect);

  // User B (Default: Faisal Khan)
  const userBGroup = document.createElement("div");
  userBGroup.className = "form-group";
  userBGroup.style.marginBottom = "0";
  const userBLabel = document.createElement("label");
  userBLabel.className = "form-label";
  userBLabel.textContent = "User B (Comparison Subject):";
  const userBSelect = document.createElement("select");
  userBSelect.className = "form-select";
  state.users.forEach(u => {
    const opt = document.createElement("option");
    opt.value = u.id;
    opt.textContent = `${u.name} (${u.role_label})`;
    if (u.id === "faisal-khan") opt.selected = true;
    userBSelect.appendChild(opt);
  });
  userBGroup.appendChild(userBLabel);
  userBGroup.appendChild(userBSelect);

  // Action
  const actionGroup = document.createElement("div");
  actionGroup.className = "form-group";
  actionGroup.style.marginBottom = "0";
  const actionLabel = document.createElement("label");
  actionLabel.className = "form-label";
  actionLabel.textContent = "Action:";
  const actionSelect = document.createElement("select");
  actionSelect.className = "form-select";
  ["check", "prepare", "file", "cancel", "override_send_back"].forEach(a => {
    const opt = document.createElement("option");
    opt.value = a;
    opt.textContent = a;
    if (a === initialAction) opt.selected = true;
    actionSelect.appendChild(opt);
  });
  actionGroup.appendChild(actionLabel);
  actionGroup.appendChild(actionSelect);

  // Job ID
  const jobGroup = document.createElement("div");
  jobGroup.className = "form-group";
  jobGroup.style.marginBottom = "0";
  const jobLabel = document.createElement("label");
  jobLabel.className = "form-label";
  jobLabel.textContent = "Shipment ID:";
  const jobInput = document.createElement("input");
  jobInput.className = "form-input";
  jobInput.value = initialJobId;
  jobGroup.appendChild(jobLabel);
  jobGroup.appendChild(jobInput);

  form.appendChild(userAGroup);
  form.appendChild(userBGroup);
  form.appendChild(actionGroup);
  form.appendChild(jobGroup);

  const btnContainer = document.createElement("div");
  btnContainer.style.gridColumn = "1 / -1";
  btnContainer.style.display = "flex";
  btnContainer.style.justifyContent = "flex-end";
  const compareBtn = document.createElement("button");
  compareBtn.className = "btn btn-primary";
  compareBtn.textContent = "Compare Decisions Side-by-Side";
  btnContainer.appendChild(compareBtn);
  form.appendChild(btnContainer);

  container.appendChild(form);

  const compareResultArea = document.createElement("div");
  container.appendChild(compareResultArea);

  const executeCompare = async () => {
    compareResultArea.innerHTML = '<div class="skeleton" style="height: 200px;"></div>';

    const uA = userASelect.value;
    const uB = userBSelect.value;
    const act = actionSelect.value;
    const jId = jobInput.value.trim();

    try {
      const data = await api.get("/explain/compare", {
        users: `${uA},${uB}`,
        action: act,
        job_id: jId,
      });

      compareResultArea.innerHTML = "";

      // Summary Card
      const summaryCard = document.createElement("div");
      summaryCard.className = "comparison-summary-card";
      const h3 = document.createElement("h4");
      h3.style.fontWeight = "700";
      h3.style.marginBottom = "6px";
      h3.textContent = "Side-by-Side Comparison Summary:";
      const p = document.createElement("p");
      p.textContent = data.comparison_summary;

      summaryCard.appendChild(h3);
      summaryCard.appendChild(p);
      compareResultArea.appendChild(summaryCard);

      // Two Column Grid
      const grid = document.createElement("div");
      grid.className = "compare-grid";

      // Col A
      const colA = document.createElement("div");
      const hColA = document.createElement("h3");
      hColA.style.fontSize = "15px";
      hColA.style.fontWeight = "700";
      hColA.style.marginBottom = "10px";
      hColA.textContent = `User A: ${uA}`;
      colA.appendChild(hColA);
      colA.appendChild(createDecisionChecklist(data.user_a_decision));

      // Col B
      const colB = document.createElement("div");
      const hColB = document.createElement("h3");
      hColB.style.fontSize = "15px";
      hColB.style.fontWeight = "700";
      hColB.style.marginBottom = "10px";
      hColB.textContent = `User B: ${uB}`;
      colB.appendChild(hColB);
      colB.appendChild(createDecisionChecklist(data.user_b_decision));

      grid.appendChild(colA);
      grid.appendChild(colB);
      compareResultArea.appendChild(grid);
    } catch (err) {
      compareResultArea.innerHTML = `
        <div class="error-state-card" style="border: none;">
          <h3>Comparison Failed</h3>
          <p>${err.message || 'Unable to execute compare query. Verify both users and shipment ID.'}</p>
        </div>
      `;
    }
  };

  compareBtn.onclick = executeCompare;
  executeCompare();
}
