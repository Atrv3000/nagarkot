/**
 * Nagarkot Access Control Service - Hash Router
 * Dispatches hash URLs (#/queue, #/jobs/:id, #/explain, etc.) to page controllers.
 */

import { state } from "./state.js";

class Router {
  constructor() {
    this.routes = [];
    this.currentRoute = null;
    this.container = null;
  }

  init(containerElement) {
    this.container = containerElement;

    window.addEventListener("hashchange", () => this.handleRoute());

    // When acting user changes, re-render active page to reflect personal queue & permissions
    state.onUserChange(() => {
      this.handleRoute(true);
    });

    this.handleRoute();
  }

  addRoute(pattern, handler) {
    // pattern can be string or regex, e.g. '#/jobs/:id'
    const paramNames = [];
    const regexPath = pattern.replace(/:([a-zA-Z0-9_]+)/g, (_, paramName) => {
      paramNames.push(paramName);
      return "([^/]+)";
    });

    this.routes.push({
      pattern,
      regex: new RegExp(`^${regexPath}$`),
      paramNames,
      handler,
    });
  }

  navigate(path) {
    window.location.hash = path.startsWith("#") ? path : `#${path}`;
  }

  async handleRoute(forceReload = false) {
    let hash = window.location.hash || "#/queue";
    if (hash === "#" || hash === "#/") {
      hash = "#/queue";
      window.location.hash = hash;
      return;
    }

    // Match route
    let matched = null;
    let params = {};

    for (const route of this.routes) {
      const match = hash.match(route.regex);
      if (match) {
        matched = route;
        route.paramNames.forEach((name, i) => {
          params[name] = decodeURIComponent(match[i + 1]);
        });
        break;
      }
    }

    this.updateActiveNav(hash);

    if (matched) {
      this.currentRoute = hash;
      try {
        await matched.handler(this.container, params);
      } catch (err) {
        console.error("Route handling error:", err);
        this.renderError(err.message || "Failed to load view.");
      }
    } else {
      this.renderNotFound();
    }
  }

  updateActiveNav(hash) {
    const navLinks = document.querySelectorAll(".nav-link");
    const baseHash = hash.split("?")[0];

    navLinks.forEach(link => {
      const href = link.getAttribute("href");
      if (href === baseHash || (baseHash.startsWith("#/jobs") && href === "#/jobs")) {
        link.classList.add("active");
        link.setAttribute("aria-current", "page");
      } else {
        link.classList.remove("active");
        link.removeAttribute("aria-current");
      }
    });
  }

  renderError(message) {
    if (!this.container) return;
    this.container.innerHTML = "";

    const div = document.createElement("div");
    div.className = "error-state-card";

    const title = document.createElement("h3");
    title.textContent = "Something went wrong";

    const p = document.createElement("p");
    p.textContent = message;

    const retryBtn = document.createElement("button");
    retryBtn.className = "btn btn-primary";
    retryBtn.textContent = "Try Again";
    retryBtn.onclick = () => this.handleRoute(true);

    div.appendChild(title);
    div.appendChild(p);
    div.appendChild(retryBtn);
    this.container.appendChild(div);
  }

  renderNotFound() {
    if (!this.container) return;
    this.container.innerHTML = "";

    const div = document.createElement("div");
    div.className = "empty-state-card";

    const title = document.createElement("h3");
    title.textContent = "Page Not Found";

    const p = document.createElement("p");
    p.textContent = "The requested view does not exist.";

    const homeBtn = document.createElement("button");
    homeBtn.className = "btn btn-primary";
    homeBtn.textContent = "Go to My Queue";
    homeBtn.onclick = () => this.navigate("#/queue");

    div.appendChild(title);
    div.appendChild(p);
    div.appendChild(homeBtn);
    this.container.appendChild(div);
  }
}

export const router = new Router();
