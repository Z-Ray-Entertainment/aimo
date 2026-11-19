(() => {
  const statusBadge = document.getElementById("admin-trans-status-badge");
  const progressText = document.getElementById("admin-trans-progress-text");
  const progressBar = document.getElementById("admin-trans-progress-bar");
  const currentTypeEl = document.getElementById("admin-trans-current-type");
  const currentTitleEl = document.getElementById("admin-trans-current-title");
  const currentLangEl = document.getElementById("admin-trans-current-lang");
  const lastFinishedEl = document.getElementById("admin-trans-last-finished");
  const lastErrorEl = document.getElementById("admin-trans-last-error");
  const syncBtn = document.getElementById("admin-trans-sync-btn");
  const cancelBtn = document.getElementById("admin-trans-cancel-btn");

  const TYPE_LABELS = {
    Character: "Character",
    Lorebook: "Lorebook",
    "Lorebook Entry": "Lorebook Entry",
    World: "World",
    WorldInfo: "World",
    Location: "Location",
    "Location Tags": "Location Tags",
    Event: "Event",
    "Character Event": "Character Event",
  };

  function tr(key) {
    return window.t ? window.t(key) : key;
  }

  function renderStatus(data) {
    if (!data) return;
    const running = Boolean(data.running);
    const paused = Boolean(data.paused);
    const completed = Number(data.completed || 0);
    const total = Number(data.total || 0);
    const pct = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0;

    if (statusBadge) {
      if (running && paused) {
        statusBadge.textContent = tr("Translation paused");
        statusBadge.style.borderColor = "#f0ad4e";
        statusBadge.style.color = "#f0ad4e";
      } else if (running) {
        statusBadge.textContent = tr("Translating...");
        statusBadge.style.borderColor = "var(--gold-accent)";
        statusBadge.style.color = "var(--gold-accent)";
      } else if (data.is_cloud) {
        statusBadge.textContent = tr("Cloud AI Mode (On-Demand)");
        statusBadge.style.borderColor = "";
        statusBadge.style.color = "";
      } else {
        statusBadge.textContent = tr("Idle");
        statusBadge.style.borderColor = "#4CAF50";
        statusBadge.style.color = "#4CAF50";
      }
    }

    if (progressText) {
      progressText.textContent = `${completed} / ${total}`;
    }
    if (progressBar) {
      progressBar.style.width = `${pct}%`;
    }

    const rawType = String(data.current_type || "").trim();
    const rawTitle = String(data.current_title || "").trim();
    const rawLang = String(data.current_language || "").trim();

    if (running && (rawTitle || data.current_item)) {
      if (currentTypeEl) {
        if (rawType) {
          currentTypeEl.textContent = tr(TYPE_LABELS[rawType] || rawType);
          currentTypeEl.style.display = "inline-flex";
        } else {
          currentTypeEl.style.display = "none";
        }
      }
      if (currentTitleEl) {
        currentTitleEl.textContent = rawTitle || data.current_item;
      }
      if (currentLangEl) {
        if (rawLang) {
          currentLangEl.textContent = rawLang;
          currentLangEl.style.display = "inline-flex";
        } else {
          currentLangEl.style.display = "none";
        }
      }
    } else {
      if (currentTypeEl) currentTypeEl.style.display = "none";
      if (currentLangEl) currentLangEl.style.display = "none";
      if (currentTitleEl) currentTitleEl.textContent = tr("No active translation");
    }

    if (lastFinishedEl) {
      lastFinishedEl.textContent = data.last_finished_at
        ? `${tr("Last finished:")} ${data.last_finished_at}`
        : "";
    }
    if (lastErrorEl) {
      lastErrorEl.textContent = data.last_error ? `${tr("Error:")} ${data.last_error}` : "";
    }
    if (syncBtn) syncBtn.disabled = running;
    if (cancelBtn) cancelBtn.disabled = !running;
  }

  async function pollStatus() {
    try {
      const resp = await fetch("/api/admin/translations/status");
      if (!resp.ok) return;
      const data = await resp.json();
      renderStatus(data);
    } catch (_) {}
  }

  if (syncBtn) {
    syncBtn.addEventListener("click", async () => {
      try {
        const resp = await fetch("/api/admin/translations/sync", { method: "POST" });
        const data = await resp.json();
        if (resp.ok && data.worker) {
          renderStatus(data.worker);
        }
      } catch (_) {}
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener("click", async () => {
      try {
        const resp = await fetch("/api/admin/translations/cancel", { method: "POST" });
        const data = await resp.json();
        if (resp.ok && data.worker) {
          renderStatus(data.worker);
        }
      } catch (_) {}
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    pollStatus();
    setInterval(pollStatus, 2000);
  });
})();
