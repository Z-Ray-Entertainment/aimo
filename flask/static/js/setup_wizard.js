(() => {
  const cfgEl = document.getElementById("setup-wizard-config");
  const cfg = cfgEl ? JSON.parse(cfgEl.textContent || "{}") : {};
  const SETUP_RECOMMENDED = cfg.recommendedByBackend || {};
  const SETUP_DEFAULT_IMG_MODEL = cfg.defaultImageModel || "";
  const SETUP_VERIFY_URL = cfg.verifyUrl || "/setup/verify-backend";
  const SETUP_PULL_URL = cfg.pullUrl || "/api/setup/models/pull";
  const SETUP_I18N = cfg.i18n || {};
  let currentStep = Number(cfg.activeStep || 1);
  let installedOllamaModels = new Set();
  let hasVerifiedOllamaOnce = false;

  function getSelectedBackend() {
    const checked = document.querySelector('input[name="llm_backend"]:checked');
    return checked ? checked.value : "ollama";
  }

  function updateStep3StepperLabel() {
    const step3Label = document.getElementById("stepper-step3-label");
    if (!step3Label) return;
    if (currentStep < 3) {
      step3Label.textContent = SETUP_I18N.configureBackend || "Configure Backend";
    } else {
      const backend = getSelectedBackend();
      step3Label.textContent =
        backend === "google_ai"
          ? (SETUP_I18N.configureGoogle || "Configure Google AI")
          : (SETUP_I18N.configureOllama || "Configure Ollama");
    }
  }

  function syncStep3Panels() {
    const backend = getSelectedBackend();
    const ollamaPanel = document.getElementById("setup-step3-ollama");
    const googlePanel = document.getElementById("setup-step3-google_ai");

    [
      [ollamaPanel, backend === "ollama"],
      [googlePanel, backend === "google_ai"],
    ].forEach(([panel, active]) => {
      if (!panel) return;
      panel.hidden = !active;
      panel.querySelectorAll("input, select, textarea").forEach((el) => {
        el.disabled = !active;
      });
    });

    updateStep3StepperLabel();
  }

  function goToSetupStep(targetStep) {
    if (targetStep > currentStep && currentStep === 1) {
      const step1Inputs = document.querySelectorAll('[data-step-pane="1"] input[required]');
      for (const inp of step1Inputs) {
        if (!inp.reportValidity()) {
          return;
        }
      }
    }

    currentStep = targetStep;
    const stepInput = document.getElementById("setup-active-step");
    if (stepInput) stepInput.value = String(targetStep);

    document.querySelectorAll("[data-step-pane]").forEach((pane) => {
      const num = parseInt(pane.getAttribute("data-step-pane"), 10);
      pane.classList.toggle("active", num === targetStep);
    });

    document.querySelectorAll("[data-step-indicator]").forEach((ind) => {
      const num = parseInt(ind.getAttribute("data-step-indicator"), 10);
      ind.classList.toggle("is-active", num === targetStep);
      ind.classList.toggle("is-done", num < targetStep);
    });

    syncStep3Panels();

    if (targetStep === 3 && getSelectedBackend() === "ollama" && !hasVerifiedOllamaOnce) {
      hasVerifiedOllamaOnce = true;
      verifySetupBackend("ollama");
    }
  }

  function updateOllamaRoleCards(textModels) {
    installedOllamaModels = new Set(textModels || []);
    document.querySelectorAll("#setup-ollama-role-cards [data-recommended-model]").forEach((row) => {
      const targetModel = row.getAttribute("data-recommended-model");
      const badge = row.querySelector(".ollama-model-check-badge");
      const pullBtn = row.querySelector(".ollama-model-pull-btn");
      if (!badge) return;
      if (installedOllamaModels.has(targetModel)) {
        badge.style.color = "#58D68D";
        badge.style.fontWeight = "700";
        badge.textContent = `✔ ${SETUP_I18N.ready || "Ready"}`;
        if (pullBtn) {
          pullBtn.hidden = true;
          pullBtn.style.display = "none";
        }
      } else {
        badge.style.color = "#F5B041";
        badge.style.fontWeight = "400";
        badge.textContent = `⏳ ${SETUP_I18N.missing || "Missing"}`;
        if (pullBtn) {
          pullBtn.hidden = false;
          pullBtn.style.display = "";
        }
      }
    });
  }

  function populateSetupSelectOptions(backend, textModels, imageModels) {
    const recMap = SETUP_RECOMMENDED[backend] || {};
    document.querySelectorAll(`select[data-role-select^="${backend}:"]`).forEach((sel) => {
      const roleKey = sel.getAttribute("data-role-select").split(":")[1];
      const preferred = sel.value || recMap[roleKey] || "";
      const options = Array.from(new Set([...(textModels || []), recMap[roleKey], preferred].filter(Boolean)));
      sel.innerHTML = "";
      options.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        if (m === preferred) opt.selected = true;
        sel.appendChild(opt);
      });
    });

    if (backend === "google_ai") {
      const imgSel = document.getElementById("setup-google-image-model");
      if (imgSel) {
        const current = imgSel.value || SETUP_DEFAULT_IMG_MODEL;
        const imgOptions = Array.from(new Set([...(imageModels || []), SETUP_DEFAULT_IMG_MODEL, current].filter(Boolean)));
        imgSel.innerHTML = "";
        imgOptions.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m;
          opt.textContent = m;
          if (m === current) opt.selected = true;
          imgSel.appendChild(opt);
        });
      }
    } else {
      updateOllamaRoleCards(textModels);
    }
  }

  async function verifySetupBackend(backend) {
    const btn = document.getElementById(backend === "google_ai" ? "verify-google-btn" : "verify-ollama-btn");
    const statusEl = document.getElementById(`setup-${backend}-status`);
    const ollamaUrl = document.getElementById("setup-ollama-url")?.value?.trim() || "";
    const apiKey = document.getElementById("setup-google-api-key")?.value?.trim() || "";

    const origHtml = window.setButtonLoading ? window.setButtonLoading(btn, SETUP_I18N.checkingConn) : null;
    if (statusEl) {
      statusEl.className = "backend-status-line is-warn";
      statusEl.textContent = `⏳ ${SETUP_I18N.checkingConnDot}`;
    }

    try {
      const resp = await fetch(SETUP_VERIFY_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          llm_backend: backend,
          ollama_url: ollamaUrl,
          google_ai_api_key: apiKey,
        }),
      });
      const data = await resp.json();
      if (data.healthy) {
        const count = Array.isArray(data.models) ? data.models.length : 0;
        if (statusEl) {
          statusEl.className = "backend-status-line is-ok";
          statusEl.textContent =
            backend === "google_ai"
              ? `✓ ${SETUP_I18N.googleValid.replace("{count}", count).replace("{img_count}", (data.image_models || []).length)}`
              : `✓ ${SETUP_I18N.ollamaReachable.replace("{count}", count)}`;
        }
        populateSetupSelectOptions(backend, data.models || [], data.image_models || []);
      } else if (statusEl) {
        statusEl.className = "backend-status-line is-err";
        statusEl.textContent = `✕ ${data.error || SETUP_I18N.connFailed}`;
        if (backend === "ollama") {
          updateOllamaRoleCards([]);
        }
      }
    } catch (_) {
      if ( backend === "ollama") {
        updateOllamaRoleCards([]);
      }
      if (statusEl) {
        statusEl.className = "backend-status-line is-err";
        statusEl.textContent = `✕ ${SETUP_I18N.connError}`;
      }
    } finally {
      if (window.resetButtonLoading && origHtml !== null) {
        window.resetButtonLoading(btn, origHtml);
      }
    }
  }

  async function pullSetupOllamaModel(modelName) {
    if (!modelName) return false;
    const box = document.getElementById("setup-pull-progress-box");
    const ollamaUrl = document.getElementById("setup-ollama-url")?.value?.trim() || "";
    const allPullBtns = document.querySelectorAll(".ollama-model-pull-btn");
    allPullBtns.forEach((b) => { b.disabled = true; });

    if (box) {
      box.style.display = "block";
      box.textContent = (SETUP_I18N.downloadingModel || "Downloading model '{model}'...").replace("{model}", modelName);
    }

    try {
      const resp = await fetch(SETUP_PULL_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: modelName, ollama_url: ollamaUrl }),
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let hasError = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        for (const line of text.split("\n")) {
          if (line.startsWith("data: ")) {
            try {
              const payload = JSON.parse(line.slice(6));
              if (payload.error) {
                hasError = true;
                if (box) box.textContent = `✕ ${payload.error}`;
              } else if (payload.completed && payload.total && typeof payload.completed === "number") {
                const pct = Math.round((payload.completed / payload.total) * 100);
                if (box) box.textContent = `${payload.status || "Downloading"} '${modelName}': ${pct}%`;
              } else if (payload.status && box) {
                box.textContent = `${modelName}: ${payload.status}`;
              }
            } catch (_) {}
          }
        }
      }

      if (!hasError) {
        if (box) {
          box.textContent = `✓ ${(SETUP_I18N.modelInstalled || "Model '{model}' installed successfully!").replace("{model}", modelName)}`;
        }
        installedOllamaModels.add(modelName);
        populateSetupSelectOptions("ollama", Array.from(installedOllamaModels), []);
        await verifySetupBackend("ollama");
        return true;
      }
      return false;
    } catch (_) {
      if (box) {
        box.textContent = `✕ ${(SETUP_I18N.downloadError || "Error downloading '{model}'.").replace("{model}", modelName)}`;
      }
      return false;
    } finally {
      allPullBtns.forEach((b) => { b.disabled = false; });
    }
  }

  window.goToSetupStep = goToSetupStep;
  window.syncStep3Panels = syncStep3Panels;
  window.verifySetupBackend = verifySetupBackend;
  window.pullSetupOllamaModel = pullSetupOllamaModel;

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('input[name="llm_backend"]').forEach((radio) => {
      radio.addEventListener("change", () => {
        hasVerifiedOllamaOnce = false;
        syncStep3Panels();
      });
    });

    syncStep3Panels();
  });
})();
