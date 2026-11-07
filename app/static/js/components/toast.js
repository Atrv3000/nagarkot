/**
 * Nagarkot Access Control Service - Accessible Toast Notification Component
 */

let toastContainer = null;

function ensureContainer() {
  if (!toastContainer) {
    toastContainer = document.getElementById("toast-container");
    if (!toastContainer) {
      toastContainer = document.createElement("div");
      toastContainer.id = "toast-container";
      toastContainer.className = "toast-container";
      toastContainer.setAttribute("aria-live", "polite");
      toastContainer.setAttribute("role", "status");
      document.body.appendChild(toastContainer);
    }
  }
  return toastContainer;
}

export function showToast(message, type = "info", duration = 4000) {
  const container = ensureContainer();

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;

  const iconMap = {
    success: "✓",
    error: "✕",
    warning: "⚠",
    info: "ℹ",
  };

  const icon = document.createElement("span");
  icon.className = "toast-icon";
  icon.textContent = iconMap[type] || "ℹ";

  const text = document.createElement("div");
  text.className = "toast-message";
  text.textContent = message;

  const closeBtn = document.createElement("button");
  closeBtn.className = "toast-close";
  closeBtn.setAttribute("aria-label", "Close notification");
  closeBtn.textContent = "×";
  closeBtn.onclick = () => removeToast(toast);

  toast.appendChild(icon);
  toast.appendChild(text);
  toast.appendChild(closeBtn);

  container.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.add("toast-visible");
  });

  if (duration > 0) {
    setTimeout(() => {
      removeToast(toast);
    }, duration);
  }

  return toast;
}

function removeToast(toast) {
  if (!toast || toast.dataset.removing) return;
  toast.dataset.removing = "true";
  toast.classList.remove("toast-visible");
  setTimeout(() => {
    if (toast.parentNode) {
      toast.parentNode.removeChild(toast);
    }
  }, 250);
}
