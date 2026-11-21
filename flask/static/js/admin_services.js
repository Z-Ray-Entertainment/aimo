(() => {
  const cfgEl = document.getElementById("admin-services-config");
  const cfg = cfgEl ? JSON.parse(cfgEl.textContent || "{}") : {};
  const RECOMMENDED_BY_BACKEND = cfg.recommendedByBackend || {};
  const RECOMMENDED_GOOGLE_IMAGE_MODEL = cfg.recommendedGoogleImageModel || "";
  const INITIAL_BACKEND = cfg.initialBackend || "ollama";
  const HAS_GOOGLE_AI_API_KEY = Boolean(cfg.hasGoogleAiApiKey);
  const INSTALLED_MODELS = Array.isArray(cfg.installedModels) ? cfg.installedModels : [];
  const OLLAMA_UNIQUE_MODELS = Array.isArray(cfg.ollamaUniqueModels) ? cfg.ollamaUniqueModels : [];
  const I18N = cfg.i18n || {};

  function getSelectedAdminBackend() {
    const checked = document.querySelector('input[name="llm_backend"]:checked');
    return checked ? checked.value : INITIAL_BACKEND;
  }

  function syncAdminConditionalServices() {
    const backend = getSelectedAdminBackend();
    const isGoogle = backend === "google_ai";

    const imgSelected = document.querySelector('input[name="image_gen_backend"]:checked')?.value || "disabled";
    const comfyBox = document.getElementById("admin-comfyui-box");
    const comfyInput = document.getElementById("admin-comfyui-url");
    if (comfyBox && comfyInput) {
      const showComfy = imgSelected === "comfyui";
      comfyBox.hidden = !showComfy;
      comfyInput.required = showComfy;
    }

    const gImgBox = document.getElementById("admin-google-img-box");
    if (gImgBox) {
      gImgBox.hidden = !(isGoogle && imgSelected === "google_ai");
    }

    const searchSelected = document.querySelector('input[name="search_backend"]:checked')?.value || "disabled";
    const searxBox = document.getElementById("admin-searxng-box");
    const searxInput = document.getElementById("admin-searxng-url");
    if (searxBox && searxInput) {
      const showSearx = searchSelected === "searxng";
      searxBox.hidden = !showSearx;
      searxInput.required = showSearx;
    }
  }

  function applyRecommendedModels() {
    const backend = getSelectedAdminBackend();
    const recMap = RECOMMENDED_BY_BACKEND[backend] || RECOMMENDED_BY_BACKEND.ollama || {};
    for (const [role, modelName] of Object.entries(recMap)) {
      const select = document.querySelector(`select[name="${role}_model"]`);
      if (select) {
        let found = false;
        for (let i = 0; i < select.options.length; i++) {
          if (select.options[i].value === modelName) {
            select.selectedIndex = i;
            found = true;
            break;
          }
        }
        if (!found) {
          const opt = document.createElement("option");
          opt.value = modelName;
          opt.textContent = modelName;
          opt.selected = true;
          select.appendChild(opt);
        }
        select.style.boxShadow = "0 0 8px var(--gold-accent)";
        setTimeout(() => { select.style.boxShadow = ""; }, 1800);
      }
    }
    if (backend === "google_ai") {
      const imgSelect = document.getElementById("admin-google-image-model");
      if (imgSelect) {
        let found = false;
        for (let i = 0; i < imgSelect.options.length; i++) {
          if (imgSelect.options[i].value === RECOMMENDED_GOOGLE_IMAGE_MODEL) {
            imgSelect.selectedIndex = i;
            found = true;
            break;
          }
        }
        if (!found) {
          const opt = document.createElement("option");
          opt.value = RECOMMENDED_GOOGLE_IMAGE_MODEL;
          opt.textContent = RECOMMENDED_GOOGLE_IMAGE_MODEL;
          opt.selected = true;
          imgSelect.appendChild(opt);
        }
      }
    }
  }

  function syncAdminBackendUI(switchedByUser = false) {
    const backend = getSelectedAdminBackend();
    const isGoogle = backend === "google_ai";

    const connOllama = document.getElementById("admin-conn-ollama");
    const connGoogle = document.getElementById("admin-conn-google_ai");
    const asideOllama = document.getElementById("admin-aside-ollama");
    const asideGoogle = document.getElementById("admin-aside-google_ai");
    const ollamaUrlInput = document.getElementById("admin-ollama-url");
    const googleKeyInput = document.getElementById("admin-google-api-key");

    if (connOllama) connOllama.hidden = isGoogle;
    if (asideOllama) asideOllama.hidden = isGoogle;
    if (connGoogle) connGoogle.hidden = !isGoogle;
    if (asideGoogle) asideGoogle.hidden = !isGoogle;
    if (ollamaUrlInput) ollamaUrlInput.required = !isGoogle;
    if (googleKeyInput) {
      googleKeyInput.required = isGoogle && !HAS_GOOGLE_AI_API_KEY;
    }

    document.querySelectorAll('[data-google-only="1"]').forEach((el) => {
      el.hidden = !isGoogle;
      const radio = el.querySelector('input[type="radio"]');
      if (radio && !radio.hasAttribute("data-locked-disabled")) {
        radio.disabled = !isGoogle;
      }
    });

    if (!isGoogle) {
      const imgSelected = document.querySelector('input[name="image_gen_backend"]:checked');
      if (imgSelected && imgSelected.value === "google_ai") {
        const disabledImgRadio = document.getElementById("admin-img-disabled");
        if (disabledImgRadio) disabledImgRadio.checked = true;
      }
      const searchSelected = document.querySelector('input[name="search_backend"]:checked');
      if (searchSelected && searchSelected.value === "google_ai") {
        const disabledRadio = document.getElementById("admin-search-disabled");
        if (disabledRadio) disabledRadio.checked = true;
      }
    }

    syncAdminConditionalServices();

    if (switchedByUser) {
      applyRecommendedModels();
    }
  }

  function setPullModel(modelName) {
    const input = document.getElementById("pull-model-name");
    if (input) {
      input.value = modelName;
      input.focus();
    }
  }

  async function verifyAdminBackend(backend) {
    const btn = document.getElementById(backend === "google_ai" ? "admin-verify-google-btn" : "admin-verify-ollama-btn");
    const statusEl = document.getElementById(`admin-verify-${backend}-status`);
    const ollamaUrl = document.getElementById("admin-ollama-url")?.value?.trim() || "";
    const apiKey = document.getElementById("admin-google-api-key")?.value?.trim() || "";

    const origHtml = window.setButtonLoading ? window.setButtonLoading(btn, window.t("Checking...")) : null;
    if (statusEl) {
      statusEl.className = "backend-status-line is-warn";
      statusEl.textContent = `⏳ ${window.t("Checking connection...")}`;
    }

    try {
      const resp = await fetch("/api/admin/llm/verify", {
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
        const models = Array.isArray(data.models) ? data.models : [];
        const imageModels = Array.isArray(data.image_models) ? data.image_models : [];
        if (statusEl) {
          statusEl.className = "backend-status-line is-ok";
          statusEl.textContent =
            backend === "google_ai"
              ? `✓ ${models.length} text/vision & ${imageModels.length} image models loaded.`
              : `✓ Ollama reachable — ${models.length} installed model(s) found.`;
        }

        const recMap = RECOMMENDED_BY_BACKEND[backend] || {};
        for (const [role, recModel] of Object.entries(recMap)) {
          const select = document.querySelector(`select[name="${role}_model"]`);
          if (!select) continue;
          const prevVal = select.value;
          const list = Array.from(new Set([...models, recModel, prevVal].filter(Boolean)));
          select.innerHTML = "";
          list.forEach((m) => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m;
            if (m === prevVal) opt.selected = true;
            select.appendChild(opt);
          });
        }

        if (backend === "google_ai") {
          const imgSel = document.getElementById("admin-google-image-model");
          if (imgSel) {
            const prevImg = imgSel.value;
            const imgList = Array.from(new Set([...imageModels, RECOMMENDED_GOOGLE_IMAGE_MODEL, prevImg].filter(Boolean)));
            imgSel.innerHTML = "";
            imgList.forEach((m) => {
              const opt = document.createElement("option");
              opt.value = m;
              opt.textContent = m;
              if (m === prevImg) opt.selected = true;
              imgSel.appendChild(opt);
            });
          }
          const listEl = document.getElementById("google-available-models-list");
          const countEl = document.getElementById("google-models-count");
          if (countEl) countEl.textContent = String(models.length);
          if (listEl) {
            listEl.innerHTML = "";
            models.forEach((m) => {
              const item = document.createElement("div");
              item.style.cssText = "padding: 0.45rem 0.65rem; background: var(--bg-input); border: 1px solid var(--border-wood-dark); border-radius: 8px; font-size: 0.84rem; font-family: monospace;";
              item.textContent = m;
              listEl.appendChild(item);
            });
          }
        }
      } else if (statusEl) {
        statusEl.className = "backend-status-line is-err";
        statusEl.textContent = `✕ ${data.error || window.t("Connection failed.")}`;
      }
    } catch (_) {
      if (statusEl) {
        statusEl.className = "backend-status-line is-err";
        statusEl.textContent = `✕ ${window.t("Connection error while testing.")}`;
      }
    } finally {
      if (window.resetButtonLoading && origHtml !== null) {
        window.resetButtonLoading(btn, origHtml);
      }
    }
  }

  async function pullOllamaModel(autoReload = true) {
    const input = document.getElementById("pull-model-name");
    const btn = document.getElementById("pull-model-btn");
    const box = document.getElementById("pull-progress-box");
    const name = input.value.trim();
    if (!name) return false;

    btn.disabled = true;
    box.style.display = "block";
    box.textContent = `Downloading model '${name}'...`;

    try {
      const resp = await fetch("/api/admin/models/pull", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name }),
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
                box.textContent = `${window.t("Error")}: ${payload.error}`;
              } else if (payload.completed && payload.total) {
                const pct = Math.round((payload.completed / payload.total) * 100);
                box.textContent = `${payload.status || "Downloading"} '${name}': ${pct}%`;
              } else if (payload.status) {
                box.textContent = `${name}: ${payload.status}`;
              }
            } catch (_) {}
          }
        }
      }

      if (!hasError) {
        box.textContent = `Model '${name}' installed successfully!`;
        if (autoReload) {
          setTimeout(() => { window.location.reload(); }, 900);
        }
        return true;
      }
      return false;
    } catch (_) {
      box.textContent = `Connection error downloading '${name}'.`;
      return false;
    } finally {
      btn.disabled = false;
    }
  }

  async function pullSpecificModel(modelName) {
    setPullModel(modelName);
    await pullOllamaModel(true);
  }

  async function pullAllMissingRecommended() {
    const missing = OLLAMA_UNIQUE_MODELS.filter((m) => !INSTALLED_MODELS.includes(m));
    if (missing.length === 0) {
      const msg = I18N.allInstalled || "";
      window.showToastInfo ? window.showToastInfo(msg) : alert(msg);
      return;
    }

    const confirmPullAll = (I18N.confirmPullAll || "").replace("__COUNT__", missing.length) + "\n\n- " + missing.join("\n- ");
    if (!(await window.aimoConfirm({ message: confirmPullAll, variant: "default" }))) {
      return;
    }

    for (let i = 0; i < missing.length; i++) {
      const model = missing[i];
      setPullModel(model);
      const isLast = i === missing.length - 1;
      const success = await pullOllamaModel(isLast);
      if (!success && !isLast) {
        const confirmContinue = (I18N.confirmContinue || "").replace("__MODEL__", model);
        if (!(await window.aimoConfirm({ message: confirmContinue, variant: "default" }))) {
          break;
        }
      }
    }
  }

  async function deleteOllamaModel(modelName) {
    const confirmDelete = (I18N.confirmDelete || "").replace("__MODEL__", modelName);
    if (!(await window.aimoConfirm({ message: confirmDelete }))) return;
    const resp = await fetch(`/api/admin/models/${encodeURIComponent(modelName)}`, {
      method: "DELETE",
    });
    if (resp.ok) {
      window.location.reload();
    } else {
      const data = await resp.json();
      const errMsg = data.error || I18N.deletionFailed || "Deletion failed.";
      window.showToastError ? window.showToastError(errMsg) : alert(errMsg);
    }
  }

  window.syncAdminBackendUI = syncAdminBackendUI;
  window.syncAdminConditionalServices = syncAdminConditionalServices;
  window.setPullModel = setPullModel;
  window.applyRecommendedModels = applyRecommendedModels;
  window.verifyAdminBackend = verifyAdminBackend;
  window.pullSpecificModel = pullSpecificModel;
  window.pullAllMissingRecommended = pullAllMissingRecommended;
  window.pullOllamaModel = pullOllamaModel;
  window.deleteOllamaModel = deleteOllamaModel;

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('input[name="llm_backend"]').forEach((radio) => {
      radio.addEventListener("change", () => syncAdminBackendUI(true));
    });
    document.querySelectorAll('input[name="image_gen_backend"], input[name="search_backend"]').forEach((radio) => {
      radio.addEventListener("change", syncAdminConditionalServices);
    });
    syncAdminBackendUI(false);
  });
})();
