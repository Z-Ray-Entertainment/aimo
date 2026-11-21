window.AimoModals = {
  open(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      if (modal.parentElement !== document.body) {
        document.body.appendChild(modal);
      }
      modal.classList.add("open");
      modal.setAttribute("aria-hidden", "false");
    }
  },
  close(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      if (modal.getAttribute("data-locked") === "1") {
        return;
      }
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
    }
  },
};

let activeConfirmResolver = null;

window.aimoConfirm = function aimoConfirm(options) {
  const opts = typeof options === "string" ? { message: options } : (options || {});
  const modal = document.getElementById("aimo-confirm-modal");
  const titleEl = document.getElementById("aimo-confirm-title");
  const msgEl = document.getElementById("aimo-confirm-message");
  const okBtn = document.getElementById("aimo-confirm-ok-btn");
  const cancelBtn = document.getElementById("aimo-confirm-cancel-btn");

  if (!modal || !msgEl || !okBtn || !cancelBtn) {
    return Promise.resolve(false);
  }

  if (activeConfirmResolver) {
    activeConfirmResolver(false);
    activeConfirmResolver = null;
  }

  const t = window.t || ((k) => k);
  if (titleEl) {
    titleEl.textContent = opts.title || t("Confirm action");
  }
  msgEl.textContent = opts.message || "";

  const okSpan = okBtn.querySelector("span:not(.icon-mono)") || okBtn;
  okSpan.textContent = opts.confirmText || t("Confirm");
  const cancelSpan = cancelBtn.querySelector("span:not(.icon-mono)") || cancelBtn;
  cancelSpan.textContent = opts.cancelText || t("Cancel");

  const variant = opts.variant || "danger";
  okBtn.classList.toggle("danger", variant !== "default");

  return new Promise((resolve) => {
    let settled = false;

    const cleanup = () => {
      okBtn.removeEventListener("click", onConfirm);
      cancelBtn.removeEventListener("click", onCancel);
      modal.removeEventListener("click", onBackdropClick);
      document.removeEventListener("keydown", onKeyDown, true);
      closeBtns.forEach((btn) => btn.removeEventListener("click", onCancel));
      if (activeConfirmResolver === settleFalse) {
        activeConfirmResolver = null;
      }
    };

    const settle = (result) => {
      if (settled) return;
      settled = true;
      cleanup();
      window.AimoModals.close("aimo-confirm-modal");
      resolve(result);
    };

    const settleFalse = () => settle(false);
    const onConfirm = (e) => {
      e.preventDefault();
      e.stopPropagation();
      settle(true);
    };
    const onCancel = (e) => {
      e.preventDefault();
      e.stopPropagation();
      settle(false);
    };
    const onBackdropClick = (e) => {
      if (e.target === modal) {
        settle(false);
      }
    };
    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        settle(false);
      }
    };

    const closeBtns = Array.from(modal.querySelectorAll("[data-modal-close]"));
    activeConfirmResolver = settleFalse;

    okBtn.addEventListener("click", onConfirm);
    cancelBtn.addEventListener("click", onCancel);
    modal.addEventListener("click", onBackdropClick);
    document.addEventListener("keydown", onKeyDown, true);
    closeBtns.forEach((btn) => btn.addEventListener("click", onCancel));

    window.AimoModals.open("aimo-confirm-modal");
    cancelBtn.focus();
  });
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    if (backdrop.parentElement !== document.body) {
      document.body.appendChild(backdrop);
    }
  });

  document.querySelectorAll("[data-modal-open]").forEach((trigger) => {
    trigger.addEventListener("click", (e) => {
      e.preventDefault();
      const target = trigger.getAttribute("data-modal-open");
      if (target) window.AimoModals.open(target);
    });
  });

  document.querySelectorAll("[data-modal-close]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      if (btn.closest("#aimo-confirm-modal")) return;
      e.preventDefault();
      const target = btn.getAttribute("data-modal-close");
      if (target) {
        window.AimoModals.close(target);
      } else {
        const backdrop = btn.closest(".modal-backdrop");
        if (backdrop && backdrop.id) window.AimoModals.close(backdrop.id);
      }
    });
  });

  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    if (backdrop.id === "aimo-confirm-modal") return;
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop && backdrop.id) {
        window.AimoModals.close(backdrop.id);
      }
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const confirmModal = document.getElementById("aimo-confirm-modal");
    if (confirmModal && confirmModal.classList.contains("open")) return;
    const openModals = Array.from(document.querySelectorAll(".modal-backdrop.open"));
    const topModal = openModals[openModals.length - 1];
    if (topModal && topModal.id) {
      window.AimoModals.close(topModal.id);
    }
  });

  document.addEventListener("submit", async (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    const msg = form.getAttribute("data-confirm");
    if (!msg) return;
    if (form.dataset.confirmBypass === "1") {
      delete form.dataset.confirmBypass;
      return;
    }
    e.preventDefault();
    e.stopImmediatePropagation();
    const ok = await window.aimoConfirm({
      message: msg,
      variant: form.getAttribute("data-confirm-variant") || "danger",
      confirmText: form.getAttribute("data-confirm-ok") || undefined,
    });
    if (ok) {
      form.dataset.confirmBypass = "1";
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
    }
  }, true);

  document.addEventListener("click", async (e) => {
    const trigger = e.target instanceof Element ? e.target.closest("[data-confirm]:not(form)") : null;
    if (!trigger) return;
    const msg = trigger.getAttribute("data-confirm");
    if (!msg) return;
    e.preventDefault();
    e.stopPropagation();
    const ok = await window.aimoConfirm({
      message: msg,
      variant: trigger.getAttribute("data-confirm-variant") || "danger",
      confirmText: trigger.getAttribute("data-confirm-ok") || undefined,
    });
    if (!ok) return;

    const formId = trigger.getAttribute("data-confirm-submit-form");
    if (formId) {
      const targetForm = document.getElementById(formId);
      if (targetForm) {
        targetForm.dataset.confirmBypass = "1";
        if (typeof targetForm.requestSubmit === "function") {
          targetForm.requestSubmit();
        } else {
          targetForm.submit();
        }
      }
      return;
    }

    if (trigger.tagName === "A" && trigger.getAttribute("href")) {
      window.location.href = trigger.getAttribute("href");
    }
  });
});
