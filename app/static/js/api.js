/**
 * Nagarkot Access Control Service - API Client
 * Wraps native fetch, automatically injecting the X-User-Id header and standardizing error handling.
 */

import { state } from "./state.js";

export class ApiError extends Error {
  constructor(status, detail, rawData = null) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.rawData = rawData;
  }
}

/**
 * Format API error into friendly plain-English messages.
 */
function formatErrorMessage(status, data, defaultMsg) {
  const currentName = state.currentUserObj?.name || state.currentUser || "this user";

  if (data && typeof data === "object") {
    if (typeof data.detail === "string") {
      // Clean up common FastAPI prefixes
      let d = data.detail.replace(/^(Forbidden:\s*|Unauthorized:\s*|Bad Request:\s*)/i, "");
      if (status === 403) {
        return `Permission Denied: You do not have permission to perform this action as ${currentName}. (${d})`;
      }
      return d;
    }
    if (Array.isArray(data.detail)) {
      // Pydantic validation errors
      const msgs = data.detail.map(e => `${e.loc?.slice(-1)[0] || 'field'}: ${e.msg}`).join(", ");
      return `Validation error: ${msgs}`;
    }
  }

  switch (status) {
    case 401:
      return "Authentication header missing or invalid.";
    case 403:
      return `You do not have permission to do this as ${currentName}.`;
    case 404:
      return "The requested resource was not found.";
    case 409:
      return "Conflict: Another user or concurrent process modified this job state. Please refresh.";
    case 422:
      return "Invalid form input or missing required parameter.";
    case 500:
      return "Internal server error: The decision engine safely failed closed. Please check the server logs.";
    default:
      return defaultMsg || `Unexpected server response (HTTP ${status}).`;
  }
}

async function request(path, options = {}) {
  const headers = {
    "Accept": "application/json",
    ...(options.headers || {}),
  };

  // Automatically attach active persona identity if not explicitly specified
  if (state.currentUser && !headers["X-User-Id"]) {
    headers["X-User-Id"] = state.currentUser;
  }

  if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }

  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
    });
  } catch (netErr) {
    throw new ApiError(0, "Unable to reach the server. Please verify the backend is running at http://127.0.0.1:8000.");
  }

  let data = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const errorMsg = formatErrorMessage(response.status, data, response.statusText);
    throw new ApiError(response.status, errorMsg, data);
  }

  return data;
}

export const api = {
  get(path, queryParams = {}, options = {}) {
    const search = new URLSearchParams();
    for (const [key, val] of Object.entries(queryParams)) {
      if (val !== undefined && val !== null && val !== "") {
        search.append(key, String(val));
      }
    }
    const queryString = search.toString();
    const fullPath = queryString ? `${path}?${queryString}` : path;
    return request(fullPath, { method: "GET", ...options });
  },

  post(path, body = {}) {
    return request(path, { method: "POST", body });
  },

  put(path, body = {}) {
    return request(path, { method: "PUT", body });
  },

  patch(path, body = {}) {
    return request(path, { method: "PATCH", body });
  },

  delete(path, body = {}) {
    return request(path, { method: "DELETE", body });
  },
};
