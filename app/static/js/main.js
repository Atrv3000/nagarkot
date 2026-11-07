/**
 * Nagarkot Access Control Service - Main UI Application Entry Point
 */

import { api } from "./api.js";
import { state } from "./state.js";
import { router } from "./router.js";
import { showToast } from "./components/toast.js";
import { createUserStatusBadge } from "./components/badge.js";

// Page Controllers
import { renderQueuePage } from "./pages/queue.js";
import { renderJobsListPage } from "./pages/jobs_list.js";
import { renderJobDetailPage } from "./pages/job_detail.js";
import { renderApprovalsPage } from "./pages/approvals.js";
import { renderAccessPage } from "./pages/access.js";
import { renderAuditPage } from "./pages/audit.js";
import { renderExplainPage } from "./pages/explain.js";

function setupMobileNav() {
  const menuBtn = document.getElementById("mobile-menu-btn");
  const sidebar = document.getElementById("app-sidebar");

  if (menuBtn && sidebar) {
    menuBtn.onclick = () => {
      sidebar.classList.toggle("sidebar-open");
    };

    // Close sidebar on navigation click on small screens
    sidebar.addEventListener("click", (e) => {
      if (e.target.closest(".nav-link")) {
        sidebar.classList.remove("sidebar-open");
      }
    });
  }
}

function updateTopbarUser(user) {
  const roleBadge = document.getElementById("user-role-badge");
  const absentIndicator = document.getElementById("user-absent-indicator");

  if (!user) return;

  if (roleBadge) {
    roleBadge.textContent = user.role_label || user.type.toUpperCase();
  }

  if (absentIndicator) {
    absentIndicator.innerHTML = "";
    if (user.status === "absent") {
      absentIndicator.style.display = "inline-flex";
      absentIndicator.appendChild(createUserStatusBadge("absent"));
    } else {
      absentIndicator.style.display = "none";
    }
  }
}

function setupUserSwitcher(users) {
  const select = document.getElementById("user-switcher-select");
  if (!select) return;

  select.innerHTML = "";

  const groups = {
    staff: { label: "Staff Members", items: [] },
    client: { label: "Client Organization Viewers", items: [] },
    system: { label: "Automated System Services", items: [] },
  };

  users.forEach(u => {
    if (groups[u.type]) {
      groups[u.type].items.push(u);
    } else {
      groups.staff.items.push(u);
    }
  });

  for (const [key, group] of Object.entries(groups)) {
    if (group.items.length === 0) continue;
    const optgroup = document.createElement("optgroup");
    optgroup.label = group.label;

    group.items.forEach(u => {
      const opt = document.createElement("option");
      opt.value = u.id;
      const absentTag = u.status === "absent" ? " [ABSENT]" : "";
      opt.textContent = `${u.name} — ${u.role_label}${absentTag}`;
      optgroup.appendChild(opt);
    });

    select.appendChild(optgroup);
  }

  // Set current selected value
  select.value = state.currentUser;

  select.onchange = () => {
    const newUserId = select.value;
    state.setUser(newUserId);
    const userObj = state.getUser(newUserId);
    updateTopbarUser(userObj);
    showToast(`Switched active context to ${userObj?.name || newUserId}`, "info");
  };

  // Listen to external user changes
  state.onUserChange((userId, userObj) => {
    if (select.value !== userId) {
      select.value = userId;
    }
    updateTopbarUser(userObj);
  });

  // Initial update
  updateTopbarUser(state.currentUserObj);
}

async function initApp() {
  setupMobileNav();

  const mainContent = document.getElementById("main-content");

  // Register Routes
  router.addRoute("#/queue", renderQueuePage);
  router.addRoute("#/jobs", renderJobsListPage);
  router.addRoute("#/jobs/:id", renderJobDetailPage);
  router.addRoute("#/approvals", renderApprovalsPage);
  router.addRoute("#/access", renderAccessPage);
  router.addRoute("#/audit", renderAuditPage);
  router.addRoute("#/explain", renderExplainPage);

  try {
    // 1. Fetch User Personas Directory for Switcher
    // Bootstrap request using asha-rao (with fallback to first staff) to retrieve full directory
    const BOOTSTRAP_USER = "asha-rao";
    const persistedUser = localStorage.getItem("nagarkot_acting_user");

    const users = await api.get("/users", {}, { headers: { "X-User-Id": BOOTSTRAP_USER } });
    state.setUsers(users);

    // Persisted selection in localStorage must still win on reload
    if (persistedUser && users.some(u => u.id === persistedUser)) {
      state.setUser(persistedUser, false);
    } else {
      const defaultUser = users.find(u => u.id === BOOTSTRAP_USER) || users.find(u => u.type === "staff") || users[0];
      state.setUser(defaultUser ? defaultUser.id : BOOTSTRAP_USER, false);
    }

    setupUserSwitcher(users);

    // 2. Initialize Router with content container
    router.init(mainContent);
  } catch (err) {
    console.error("App startup failure:", err);
    mainContent.innerHTML = "";
    const card = document.createElement("div");
    card.className = "error-state-card";
    const h3 = document.createElement("h3");
    h3.textContent = "Unable to connect to Nagarkot API";
    const p = document.createElement("p");
    p.textContent = err.message || "Please ensure the backend service is running.";
    const retryBtn = document.createElement("button");
    retryBtn.className = "btn btn-primary";
    retryBtn.textContent = "Retry";
    retryBtn.onclick = () => window.location.reload();

    card.appendChild(h3);
    card.appendChild(p);
    card.appendChild(retryBtn);
    mainContent.appendChild(card);
  }
}

window.addEventListener("DOMContentLoaded", initApp);
