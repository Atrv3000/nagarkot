/**
 * Nagarkot Access Control Service - My Queue Page Component
 * Shows personal actionable jobs filtered strictly by the SQL queue predicate.
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { router } from "../router.js";
import { createStageBadge } from "../components/badge.js";
import { formatRelativeTime } from "../labels.js";
import { escapeHtml } from "../utils.js";

let currentCursor = null;
let queueItems = [];
let totalCount = 0;

export async function renderQueuePage(container) {
  const currentName = state.currentUserObj?.name || state.currentUser;
  document.getElementById("view-heading").textContent = "My Actionable Queue";
  container.innerHTML = "";

  // Reset pagination state
  currentCursor = null;
  queueItems = [];

  const card = document.createElement("div");
  card.className = "card";

  const header = document.createElement("div");
  header.className = "card-header";

  const titleGroup = document.createElement("div");
  const title = document.createElement("h2");
  title.className = "card-title";
  title.id = "queue-card-title";
  title.textContent = `Action Queue for ${currentName}`;

  const subtitle = document.createElement("div");
  subtitle.className = "card-subtitle";
  subtitle.id = "queue-card-subtitle";
  subtitle.textContent = "Loading actionable shipments...";

  titleGroup.appendChild(title);
  titleGroup.appendChild(subtitle);

  const headerActions = document.createElement("div");
  const refreshBtn = document.createElement("button");
  refreshBtn.className = "btn btn-secondary";
  refreshBtn.innerHTML = "<span>↻</span> Refresh";
  refreshBtn.onclick = () => loadQueue(tableBody, subtitle, paginationContainer, true);

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
  ["Shipment Ref", "Client", "Branch", "Direction", "Mode", "Stage", "Assigned To", "Updated"].forEach(col => {
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

  // Initial load
  await loadQueue(tableBody, subtitle, paginationContainer, true);
}

async function loadQueue(tbody, subtitleEl, paginationEl, isFirstPage = false) {
  if (isFirstPage) {
    currentCursor = null;
    queueItems = [];
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="padding: 32px; text-align: center;">
          <div class="skeleton" style="width: 60%; margin: 0 auto 12px;"></div>
          <div class="skeleton" style="width: 40%; margin: 0 auto;"></div>
        </td>
      </tr>
    `;
  }

  try {
    const params = { limit: 25 };
    if (currentCursor) {
      params.cursor = currentCursor;
    }

    const data = await api.get("/me/queue", params);
    totalCount = data.count;
    currentCursor = data.next_cursor;

    const currentName = state.currentUserObj?.name || state.currentUser;
    subtitleEl.textContent = `${totalCount} shipment${totalCount === 1 ? '' : 's'} waiting for action by ${currentName}`;

    if (isFirstPage) {
      tbody.innerHTML = "";
    }

    if (data.items.length === 0 && queueItems.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8">
            <div class="empty-state-card" style="border: none; margin: 12px 0;">
              <h3>Your Queue is Empty</h3>
              <p>There are no shipments currently waiting for your action. You can inspect all visible jobs or switch personas above.</p>
              <a href="#/jobs" class="btn btn-secondary">Browse All Shipments</a>
            </div>
          </td>
        </tr>
      `;
      paginationEl.innerHTML = "";
      return;
    }

    data.items.forEach(job => {
      queueItems.push(job);
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

      // Assigned To
      const tdAssign = document.createElement("td");
      tdAssign.textContent = job.assigned_to || "Unassigned (Pool)";

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
      row.appendChild(tdAssign);
      row.appendChild(tdUpdated);

      tbody.appendChild(row);
    });

    // Render pagination
    paginationEl.innerHTML = "";
    const info = document.createElement("span");
    info.className = "pagination-info";
    info.textContent = `Showing ${queueItems.length} of ${totalCount} actionable shipments`;
    paginationEl.appendChild(info);

    if (currentCursor) {
      const loadMoreBtn = document.createElement("button");
      loadMoreBtn.className = "btn btn-secondary";
      loadMoreBtn.textContent = "Load More Shipments ↓";
      loadMoreBtn.onclick = async () => {
        loadMoreBtn.disabled = true;
        loadMoreBtn.textContent = "Loading...";
        await loadQueue(tbody, subtitleEl, paginationEl, false);
      };
      paginationEl.appendChild(loadMoreBtn);
    }
  } catch (err) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8">
          <div class="error-state-card" style="border: none; margin: 12px 0;">
            <h3>Failed to load queue</h3>
            <p>${escapeHtml(err.message || 'Error communicating with access service.')}</p>
          </div>
        </td>
      </tr>
    `;
  }
}
