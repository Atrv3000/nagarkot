/**
 * Nagarkot Access Control Service - All Shipments (Jobs) List View
 * Shows all shipments visible to the active user based on their visibility scope.
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { router } from "../router.js";
import { createStageBadge } from "../components/badge.js";
import { formatRelativeTime } from "../labels.js";
import { escapeHtml } from "../utils.js";

let currentCursor = null;
let allJobs = [];
let totalCount = 0;

export async function renderJobsListPage(container) {
  const currentName = state.currentUserObj?.name || state.currentUser;
  document.getElementById("view-heading").textContent = "All Shipments (Jobs)";
  container.innerHTML = "";

  currentCursor = null;
  allJobs = [];

  const card = document.createElement("div");
  card.className = "card";

  const header = document.createElement("div");
  header.className = "card-header";

  const titleGroup = document.createElement("div");
  const title = document.createElement("h2");
  title.className = "card-title";
  title.textContent = "Visible Shipments Directory";

  const subtitle = document.createElement("div");
  subtitle.className = "card-subtitle";
  subtitle.textContent = `Showing all shipments visible to ${currentName}`;

  titleGroup.appendChild(title);
  titleGroup.appendChild(subtitle);

  const headerActions = document.createElement("div");
  headerActions.style.display = "flex";
  headerActions.style.alignItems = "center";
  headerActions.style.gap = "8px";

  const searchInput = document.createElement("input");
  searchInput.type = "text";
  searchInput.className = "form-input";
  searchInput.placeholder = "Search loaded jobs (e.g. SOD, SHOWCASE)...";
  searchInput.style.maxWidth = "260px";
  searchInput.style.padding = "6px 12px";
  searchInput.oninput = () => {
    const term = searchInput.value.trim().toLowerCase();
    const rows = tableBody.querySelectorAll("tr.clickable");
    rows.forEach(r => {
      const text = r.textContent.toLowerCase();
      r.style.display = text.includes(term) ? "" : "none";
    });
  };

  const refreshBtn = document.createElement("button");
  refreshBtn.className = "btn btn-secondary";
  refreshBtn.innerHTML = "<span>↻</span> Refresh";
  refreshBtn.onclick = () => loadJobs(tableBody, subtitle, paginationContainer, true);

  headerActions.appendChild(searchInput);
  headerActions.appendChild(refreshBtn);
  header.appendChild(titleGroup);
  header.appendChild(headerActions);

  const body = document.createElement("div");
  body.className = "card-body";

  // Showcase Demo Quick Jump Bar
  const showcaseBar = document.createElement("div");
  showcaseBar.style.display = "flex";
  showcaseBar.style.flexWrap = "wrap";
  showcaseBar.style.alignItems = "center";
  showcaseBar.style.gap = "8px";
  showcaseBar.style.marginBottom = "16px";
  showcaseBar.style.padding = "10px 14px";
  showcaseBar.style.backgroundColor = "var(--bg-app)";
  showcaseBar.style.border = "1px solid var(--border-color)";
  showcaseBar.style.borderRadius = "var(--radius-md)";
  showcaseBar.style.fontSize = "12px";

  const label = document.createElement("span");
  label.style.fontWeight = "700";
  label.style.color = "var(--text-muted)";
  label.textContent = "⭐ Showcase Demo Shipments:";
  showcaseBar.appendChild(label);

  const showcaseJobs = [
    { id: "JOB-SHOWCASE-01", label: "01 (Filed)" },
    { id: "JOB-SHOWCASE-02", label: "02 (SoD Conflict)" },
    { id: "JOB-SHOWCASE-03", label: "03 (Stuck)" },
    { id: "JOB-SHOWCASE-04", label: "04 (Arjun Revoked)" },
    { id: "JOB-SHOWCASE-05", label: "05 (Rohit Import)" },
    { id: "JOB-SHOWCASE-06", label: "06 (Export Deny)" },
    { id: "JOB-SHOWCASE-07", label: "07 (Branch Deny)" },
    { id: "JOB-SHOWCASE-08", label: "08 (Delhi Cover)" },
    { id: "JOB-HIST-DEMO-01", label: "Oct 3 Time-Travel (Hist-01)" },
  ];

  showcaseJobs.forEach(sj => {
    const link = document.createElement("a");
    link.href = `#/jobs/${encodeURIComponent(sj.id)}`;
    link.className = "btn btn-secondary";
    link.style.padding = "4px 8px";
    link.style.fontSize = "11px";
    link.textContent = sj.label;
    showcaseBar.appendChild(link);
  });

  body.appendChild(showcaseBar);

  const tableWrapper = document.createElement("div");
  tableWrapper.className = "table-container";

  const table = document.createElement("table");
  table.className = "data-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Shipment Ref", "Client", "Branch", "Direction", "Mode", "Stage", "Cycle", "Assigned To", "Updated"].forEach(col => {
    const th = document.createElement("th");
    th.textContent = col;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);

  const tableBody = document.createElement("tbody");
  table.appendChild(thead);
  table.appendChild(tableBody);
  tableWrapper.appendChild(table);

  const paginationContainer = document.createElement("div");
  paginationContainer.className = "pagination-bar";

  body.appendChild(tableWrapper);
  body.appendChild(paginationContainer);

  card.appendChild(header);
  card.appendChild(body);
  container.appendChild(card);

  await loadJobs(tableBody, subtitle, paginationContainer, true);
}

async function loadJobs(tbody, subtitleEl, paginationEl, isFirstPage = false) {
  if (isFirstPage) {
    currentCursor = null;
    allJobs = [];
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="padding: 32px; text-align: center;">
          <div class="skeleton" style="width: 60%; margin: 0 auto 12px;"></div>
          <div class="skeleton" style="width: 40%; margin: 0 auto;"></div>
        </td>
      </tr>
    `;
  }

  try {
    const params = { limit: 25 };
    if (currentCursor) params.cursor = currentCursor;

    const data = await api.get("/jobs", params);
    totalCount = data.count;
    currentCursor = data.next_cursor;

    const currentName = state.currentUserObj?.name || state.currentUser;
    subtitleEl.textContent = `${totalCount} shipment${totalCount === 1 ? '' : 's'} visible to ${currentName}`;

    if (isFirstPage) {
      tbody.innerHTML = "";
    }

    if (data.items.length === 0 && allJobs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9">
            <div class="empty-state-card" style="border: none;">
              <h3>No Shipments Visible</h3>
              <p>Your current user grants do not cover viewing any shipments in the database.</p>
            </div>
          </td>
        </tr>
      `;
      paginationEl.innerHTML = "";
      return;
    }

    data.items.forEach(job => {
      allJobs.push(job);
      const row = document.createElement("tr");
      row.className = "clickable";
      row.onclick = () => router.navigate(`#/jobs/${encodeURIComponent(job.id)}`);

      // Ref
      const tdRef = document.createElement("td");
      const refBold = document.createElement("strong");
      refBold.style.color = "var(--primary)";
      refBold.textContent = job.ref;
      tdRef.appendChild(refBold);

      const idSub = document.createElement("div");
      idSub.style.fontSize = "11px";
      idSub.style.color = "var(--text-muted)";
      idSub.style.fontFamily = "var(--font-mono)";
      idSub.textContent = job.id;
      tdRef.appendChild(idSub);

      // Client
      const tdClient = document.createElement("td");
      tdClient.textContent = job.client_id;

      // Branch
      const tdBranch = document.createElement("td");
      tdBranch.textContent = job.branch_id;

      // Direction
      const tdDir = document.createElement("td");
      tdDir.textContent = job.direction;

      // Mode
      const tdMode = document.createElement("td");
      tdMode.textContent = job.mode;

      // Stage
      const tdStage = document.createElement("td");
      tdStage.appendChild(createStageBadge(job.stage));

      // Cycle
      const tdCycle = document.createElement("td");
      tdCycle.textContent = String(job.cycle || 1);

      // Assigned To
      const tdAssign = document.createElement("td");
      tdAssign.textContent = job.assigned_to || (state.currentUserObj?.type === "client" ? "—" : "Unassigned");

      // Updated
      const tdUpdated = document.createElement("td");
      tdUpdated.textContent = formatRelativeTime(job.updated_at);
      tdUpdated.title = new Date(job.updated_at).toLocaleString();

      row.appendChild(tdRef);
      row.appendChild(tdClient);
      row.appendChild(tdBranch);
      row.appendChild(tdDir);
      row.appendChild(tdMode);
      row.appendChild(tdStage);
      row.appendChild(tdCycle);
      row.appendChild(tdAssign);
      row.appendChild(tdUpdated);

      tbody.appendChild(row);
    });

    // Pagination
    paginationEl.innerHTML = "";
    const info = document.createElement("span");
    info.className = "pagination-info";
    info.textContent = `Showing ${allJobs.length} of ${totalCount} visible shipments`;
    paginationEl.appendChild(info);

    if (currentCursor) {
      const loadMoreBtn = document.createElement("button");
      loadMoreBtn.className = "btn btn-secondary";
      loadMoreBtn.textContent = "Load More Shipments ↓";
      loadMoreBtn.onclick = async () => {
        loadMoreBtn.disabled = true;
        loadMoreBtn.textContent = "Loading...";
        await loadJobs(tbody, subtitleEl, paginationEl, false);
      };
      paginationEl.appendChild(loadMoreBtn);
    }
  } catch (err) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9">
          <div class="error-state-card" style="border: none;">
            <h3>Error Loading Shipments</h3>
            <p>${escapeHtml(err.message || 'Unable to load shipments list.')}</p>
          </div>
        </td>
      </tr>
    `;
  }
}
