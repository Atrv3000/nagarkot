/**
 * Nagarkot Access Control Service - Utility Functions
 */

/**
 * Safely escape HTML special characters to prevent XSS injection.
 * Handles &, <, >, ", and ' and returns "" for null or undefined.
 *
 * @param {any} value
 * @returns {string}
 */
export function escapeHtml(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
