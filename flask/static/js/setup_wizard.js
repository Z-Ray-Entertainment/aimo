(() => {
  const cfgEl = document.getElementById("setup-wizard-config");
  const cfg = cfgEl ? JSON.parse(cfgEl.textContent || "{}") : {};
  const SETUP_RECOMMENDED = cfg.recommendedByBackend || {};
  const SETUP_DEFAULT_IMG_MODEL = cfg.defaultImageModel || "";
  const SETUP_VERIFY_URL = cfg.verifyUrl || "/setup/verify-backend";
  const SETUP_I18N = cfg.i18n || {};
  let currentStep = Number(cfg.activeStep || 1);

  function getSelectedBackend() {
    const checked = document.querySelector('input[name="llm_backend"]:checked');
    return checked ? checked.value : "ollama";
  }

  function syncConditionalSubservices(backend) {
    const prefix = backend === "google_ai" ? "setup-google" : "setup-ollama";
    const panel = document.getElementById(backend === "google_ai" ? "setup-step3-google_ai" : "setup-step3-ollama");
    if (!panel) return;

    const imgRadio = panel.querySelector('input[name="image_gen_backend"]:checked');
    const imgChoice = imgRadio ? imgRadio.value : "disabled";
    const comfyBox = document.getElementById(`${prefix}-comfy-box`);
    const comfyInput = document.getElementById(`${prefix}-comfyui-url`);
    if (comfyBox && comfyInput) {
      const showComfy = imgChoice === "comfyui";
      comfyBox.hidden = !showComfy;
      comfyInput.disabled = !showComfy || panel.hidden;
      comfyInput.required = showComfy && !panel.hidden;
    }

    if (backend === "google_ai") {
      const gImgBox = document.getElementById("setup-google-image-model-box");
      const gImgSelect = document.getElementById("setup-google-image-model");
      if (gImgBox && gImgSelect) {
        const showGImg = imgChoice === "google_ai";
        gImgBox.hidden = !showGImg;
        gImgSelect.disabled = !showGImg || panel.hidden;
      }
    }

    const searchRadio = panel.querySelector('input[name="search_backend"]:checked');
    const searchChoice = searchRadio ? searchRadio.value : "disabled";
    const searxBox = document.getElementById(`${prefix}-searxng-box`);
    const searxInput = document.getElementById(`${prefix}-searxng-url`);
    if (searxBox && searxInput) {
      const showSearx = searchChoice === "searxng";
      searxBox.hidden = !showSearx;
      searxInput.disabled = !showSearx || panel.hidden;
      searxInput.required = showSearx && !panel.hidden;
    }
  }

  function syncStep3Panels() {
    const backend = getSelectedBackend();
    const ollamaPanel = document.getElementById("setup-step3-ollama");
    const googlePanel = document.getElementById("setup-step3-google_ai");
    const step3Label = document.getElementById("stepper-step3-label");

    [
      [ollamaPanel, backend === "ollama", { image_gen_backend: "disabled", search_backend: "disabled" }],
      [googlePanel, backend === "google_ai", { image_gen_backend: "disabled", search_backend: "disabled" }],
    ].forEach(([panel, active, defaults]) => {
      if (!panel) return;
      panel.hidden = !active;
      panel.querySelectorAll("input, select, textarea").forEach((el) => {
        if (el.type === "radio") {
          const fieldName = el.dataset.fieldName || el.getAttribute("name");
          if (fieldName) {
            el.dataset.fieldName = fieldName;
          }
          if (active && el.dataset.fieldName) {
            el.setAttribute("name", el.dataset.fieldName);
          } else if (!active) {
            el.removeAttribute("name");
          }
        }
        el.disabled = !active;
      });

      if (active) {
        Object.entries(defaults).forEach(([groupName, fallbackVal]) => {
          const groupRadios = Array.from(
            panel.querySelectorAll(`input[type="radio"][name="${groupName}"]`)
          );
          if (groupRadios.length > 0 && !groupRadios.some((r) => r.checked)) {
            const targetRadio =
              groupRadios.find((r) => r.defaultChecked) ||
              groupRadios.find((r) => r.value === fallbackVal) ||
              groupRadios[0];
            if (targetRadio) targetRadio.checked = true;
          }
        });
      }
    });

    if (step3Label) {
      step3Label.textContent = backend === "google_ai" ? SETUP_I18N.configureGoogle : SETUP_I18N.configureOllama;
    }
    syncConditionalSubservices(backend);
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

    if (targetStep === 3) {
      syncStep3Panels();
    }
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
      const installedSet = new Set(textModels || []);
      document.querySelectorAll("#setup-ollama-role-cards [data-recommended-model]").forEach((row) => {
        const targetModel = row.getAttribute("data-recommended-model");
        const badge = row.querySelector(".ollama-model-check-badge");
        if (!badge) return;
        if (installedSet.has(targetModel)) {
          badge.style.color = "#58D68D";
          badge.textContent = `✔ ${SETUP_I18N.ready}`;
        } else {
          badge.style.color = "#F5B041";
          badge.textContent = `⏳ ${SETUP_I18N.missing}`;
        }
      });
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
      }
    } catch (_) {
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

  window.goToSetupStep = goToSetupStep;
  window.syncStep3Panels = syncStep3Panels;
  window.syncConditionalSubservices = syncConditionalSubservices;
  window.verifySetupBackend = verifySetupBackend;

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('input[name="llm_backend"]').forEach((radio) => {
      radio.addEventListener("change", () => {
        if (currentStep === 3) {
          syncStep3Panels();
        }
      });
    });

    document.querySelectorAll('input[name="image_gen_backend"], input[name="search_backend"]').forEach((radio) => {
      radio.addEventListener("change", () => {
        syncConditionalSubservices(getSelectedBackend());
      });
    });

    syncStep3Panels();
  });
})();
