document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".btn-reset-prompt").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetName = btn.dataset.target;
      if (!targetName) return;

      if (!confirm(window.t("Reset this prompt in all languages back to the built-in default?"))) {
        return;
      }

      const textarea = document.querySelector(`textarea[name="${targetName}"]`);
      if (!textarea) return;

      const hiddenId = textarea.getAttribute("data-i18n-hidden");
      const hiddenEl = hiddenId ? document.getElementById(hiddenId) : null;
      const defaultVariantsRaw = textarea.getAttribute("data-default-variants");
      if (hiddenEl && defaultVariantsRaw) {
        hiddenEl.value = defaultVariantsRaw;
      }

      textarea.value = textarea.dataset.defaultPrompt || "";
      textarea.dispatchEvent(new CustomEvent("aimo:i18n-reload", { bubbles: true }));

      if (window.showToastSuccess) {
        window.showToastSuccess("Default prompt restored for all languages. Click 'Save Prompts' to apply.");
      }
    });
  });

  const syncBtn = document.getElementById("btn-sync-translations");
  const cancelBtn = document.getElementById("btn-cancel-translations");
  const statusEl = document.getElementById("translation-sync-status");
  let pollTimer = null;

  const renderSyncStatus = (st) => {
    if (!statusEl || !st) return;
    if (st.running) {
      statusEl.style.display = "block";
      const pct = st.total > 0 ? Math.round((st.completed / st.total) * 100) : 0;
      statusEl.textContent = `Translating: ${st.completed} / ${st.total} (${pct}%) — ${st.current_item || "..."}`;
      if (cancelBtn) cancelBtn.classList.remove("hidden");
      if (syncBtn) syncBtn.disabled = true;
    } else {
      if (cancelBtn) cancelBtn.classList.add("hidden");
      if (syncBtn) syncBtn.disabled = false;
      if (st.last_error) {
        statusEl.style.display = "block";
        statusEl.textContent = `Last sync error: ${st.last_error}`;
      } else if (st.total > 0 && st.completed >= st.total) {
        statusEl.style.display = "block";
        statusEl.textContent = `Sync completed (${st.completed} / ${st.total}).`;
      }
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }
  };

  const pollStatus = async () => {
    try {
      const resp = await fetch("/api/admin/translations/status");
      if (resp.ok) {
        const data = await resp.json();
        renderSyncStatus(data);
        return data;
      }
    } catch (_) {}
    return null;
  };

  if (syncBtn) {
    pollStatus().then((st) => {
      if (st && st.running && !pollTimer) {
        pollTimer = setInterval(pollStatus, 2000);
      }
    });

    syncBtn.addEventListener("click", async () => {
      try {
        const resp = await fetch("/api/admin/translations/sync", { method: "POST" });
        if (resp.ok) {
          const data = await resp.json();
          if (statusEl) {
            statusEl.style.display = "block";
            statusEl.textContent = "Starting translation synchronization...";
          }
          renderSyncStatus(data.worker);
          if (!pollTimer) {
            pollTimer = setInterval(pollStatus, 2000);
          }
        }
      } catch (_) {}
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener("click", async () => {
      try {
        await fetch("/api/admin/translations/cancel", { method: "POST" });
      } catch (_) {}
    });
  }
});
