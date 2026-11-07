/**
 * Nagarkot Access Control Service - Accessible Modal Dialog Component
 */

let activeModal = null;

export function openModal({
  title = "Confirm Action",
  contentElement,
  confirmText = "Confirm",
  confirmClass = "btn-primary",
  cancelText = "Cancel",
  onConfirm = null,
}) {
  closeModal();

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";

  const dialog = document.createElement("div");
  dialog.className = "modal-dialog";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "modal-title");

  // Header
  const header = document.createElement("div");
  header.className = "modal-header";

  const titleEl = document.createElement("h3");
  titleEl.id = "modal-title";
  titleEl.className = "modal-title";
  titleEl.textContent = title;

  const closeBtn = document.createElement("button");
  closeBtn.className = "modal-close";
  closeBtn.setAttribute("aria-label", "Close modal");
  closeBtn.textContent = "×";
  closeBtn.onclick = closeModal;

  header.appendChild(titleEl);
  header.appendChild(closeBtn);

  // Body
  const body = document.createElement("div");
  body.className = "modal-body";
  if (contentElement) {
    if (typeof contentElement === "string") {
      body.textContent = contentElement;
    } else {
      body.appendChild(contentElement);
    }
  }

  // Footer
  const footer = document.createElement("div");
  footer.className = "modal-footer";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "btn btn-secondary";
  cancelBtn.textContent = cancelText;
  cancelBtn.onclick = closeModal;

  const confirmBtn = document.createElement("button");
  confirmBtn.type = "button";
  confirmBtn.className = `btn ${confirmClass}`;
  confirmBtn.textContent = confirmText;

  confirmBtn.onclick = async () => {
    if (onConfirm) {
      confirmBtn.disabled = true;
      confirmBtn.textContent = "Processing...";
      try {
        const result = await onConfirm();
        if (result !== false) {
          closeModal();
        }
      } catch (err) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = confirmText;
      }
    } else {
      closeModal();
    }
  };

  footer.appendChild(cancelBtn);
  footer.appendChild(confirmBtn);

  dialog.appendChild(header);
  dialog.appendChild(body);
  dialog.appendChild(footer);
  backdrop.appendChild(dialog);

  // Dismiss on backdrop click
  backdrop.onclick = (e) => {
    if (e.target === backdrop) {
      closeModal();
    }
  };

  // Keyboard accessibility: ESC to close
  const onKeyDown = (e) => {
    if (e.key === "Escape") {
      closeModal();
    }
  };
  document.addEventListener("keydown", onKeyDown);

  document.body.appendChild(backdrop);
  document.body.classList.add("modal-open");

  activeModal = { backdrop, onKeyDown };

  // Focus confirm or input
  setTimeout(() => {
    const input = dialog.querySelector("input, textarea, select");
    if (input) {
      input.focus();
    } else {
      confirmBtn.focus();
    }
  }, 50);

  return { closeModal, confirmBtn };
}

export function closeModal() {
  if (activeModal) {
    document.removeEventListener("keydown", activeModal.onKeyDown);
    if (activeModal.backdrop.parentNode) {
      activeModal.backdrop.parentNode.removeChild(activeModal.backdrop);
    }
    document.body.classList.remove("modal-open");
    activeModal = null;
  }
}
