window.AimoModals = {
  open(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add("open");
      modal.setAttribute("aria-hidden", "false");
    }
  },
  close(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-modal-open]").forEach((trigger) => {
    trigger.addEventListener("click", (e) => {
      e.preventDefault();
      const target = trigger.getAttribute("data-modal-open");
      if (target) window.AimoModals.open(target);
    });
  });

  document.querySelectorAll("[data-modal-close]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
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
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop && backdrop.id) {
        window.AimoModals.close(backdrop.id);
      }
    });
  });
});
