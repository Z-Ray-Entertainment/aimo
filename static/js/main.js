document.addEventListener("DOMContentLoaded", () => {
  // Generic Tab Switcher
  document.querySelectorAll("[data-tab-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab-target");
      const group = btn.closest("[data-tab-group]") || document;
      group.querySelectorAll("[data-tab-target]").forEach((b) => b.classList.remove("active"));
      group.querySelectorAll(".tab-pane").forEach((pane) => pane.classList.remove("active"));
      btn.classList.add("active");
      const pane = document.getElementById(targetId);
      if (pane) {
        pane.classList.add("active");
      }
    });
  });

  // Dynamic Heart Icon & Color helper for relationship bars
  document.querySelectorAll("[data-relationship-score]").forEach((el) => {
    const score = parseFloat(el.getAttribute("data-relationship-score") || "0");
    const pct = Math.max(0, Math.min(100, ((score + 100) / 200) * 100));
    const fill = el.querySelector(".relationship-fill");
    const heartIcon = el.querySelector(".heart-icon");
    if (fill) {
      fill.style.width = `${pct}%`;
    }
    if (heartIcon) {
      if (score <= -60) {
        heartIcon.textContent = "💔";
        heartIcon.style.color = "#7A1C1C";
      } else if (score < 0) {
        heartIcon.textContent = "❤️‍🩹";
        heartIcon.style.color = "#A93226";
      } else if (score < 50) {
        heartIcon.textContent = "❤️";
        heartIcon.style.color = "#E74C3C";
      } else {
        heartIcon.textContent = "💖";
        heartIcon.style.color = "#FF69B4";
      }
    }
  });
});
