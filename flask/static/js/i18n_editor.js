// Multi-language Editor Toolbar & Flag Pill-Badges for [data-i18n-field]
if (!window.AIMO_I18N_EDITOR_LOADED) {
  window.AIMO_I18N_EDITOR_LOADED = true;

const AIMO_LANGUAGES = Array.isArray(window.AIMO_LANGUAGES) && window.AIMO_LANGUAGES.length
  ? window.AIMO_LANGUAGES
  : [
      { code: "en", flag: "🇬🇧", label: "English" },
      { code: "de", flag: "🇩🇪", label: "Deutsch" },
    ];

function initEditorI18nFields() {
  document.querySelectorAll("[data-i18n-field]").forEach((inputEl) => {
    if (inputEl.getAttribute("data-i18n-initialized") === "1") return;
    inputEl.setAttribute("data-i18n-initialized", "1");

    const fieldName = inputEl.getAttribute("data-i18n-field") || "";
    const entityType = inputEl.getAttribute("data-i18n-entity-type") || "";
    let entityId = inputEl.getAttribute("data-i18n-entity-id") || "";
    const hiddenId = inputEl.getAttribute("data-i18n-hidden") || "";
    const hiddenInput = hiddenId ? document.getElementById(hiddenId) : null;

    let rawParsed = {};
    if (hiddenInput && hiddenInput.value) {
      try {
        rawParsed = JSON.parse(hiddenInput.value) || {};
      } catch (_) {
        rawParsed = {};
      }
    }

    const rawVariants =
      rawParsed && typeof rawParsed.variants === "object" && rawParsed.variants !== null
        ? rawParsed.variants
        : rawParsed;

    const variants = {};
    Object.keys(rawVariants || {}).forEach((code) => {
      const item = rawVariants[code];
      if (item && typeof item === "object") {
        const txt = String(item.content ?? item.text ?? "");
        const out = Boolean(item.is_outdated ?? item.outdated ?? false);
        variants[code] = { content: txt, text: txt, is_outdated: out, outdated: out };
      }
    });

    const rawSysLang = (document.body.dataset.userLanguage || navigator.language || "en").slice(0, 2).toLowerCase();
    const sysLang = AIMO_LANGUAGES.some((l) => l.code === rawSysLang) ? rawSysLang : "en";
    const explicitOrigin = (inputEl.getAttribute("data-i18n-origin") || "").slice(0, 2).toLowerCase();

    let originLang =
      (explicitOrigin && AIMO_LANGUAGES.some((l) => l.code === explicitOrigin) ? explicitOrigin : "") ||
      Object.keys(variants)[0] ||
      sysLang;

    const initialText = inputEl.value || "";
    if (initialText.trim() && Object.keys(variants).length === 0) {
      variants[originLang] = {
        content: initialText,
        text: initialText,
        is_outdated: false,
        outdated: false,
      };
    }

    let activeLang = sysLang;

    if (variants[activeLang] && typeof variants[activeLang].content === "string") {
      inputEl.value = variants[activeLang].content;
    } else if (Object.keys(variants).length > 0) {
      inputEl.value = "";
    }

    // Track whether the user is currently providing/fixing a translation so we don't mark the origin language outdated while they type a new translation
    let isProvidingTranslation = activeLang !== originLang;
    let dirtyInCurrentTab = false;
    inputEl.dataset.i18nActiveLang = activeLang;

    const toolbar = document.createElement("div");
    toolbar.className = "i18n-toolbar";

    const leftGroup = document.createElement("div");
    leftGroup.className = "i18n-left-group";

    // Country Flags Container
    const flagsContainer = document.createElement("div");
    flagsContainer.className = "i18n-flags-list";

    leftGroup.appendChild(flagsContainer);

    // 3. AI Translate button (translates into currently active language from origin/English)
    const controlsContainer = document.createElement("div");
    controlsContainer.className = "i18n-translate-controls";

    const isFieldDisabled = Boolean(inputEl.disabled);

    const translateBtn = document.createElement("button");
    translateBtn.type = "button";
    translateBtn.className = "aimo-btn aimo-btn-sm";
    translateBtn.title = "Auto-translate from origin/English into the selected language";
    translateBtn.innerHTML = `<span class="icon-mono">🌐</span><span>AI Translate</span>`;
    if (isFieldDisabled) translateBtn.disabled = true;

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "aimo-btn aimo-btn-sm aimo-btn-icon danger";
    deleteBtn.title = window.t ? window.t("Delete translation for this language") : "Delete translation for this language";
    deleteBtn.setAttribute("aria-label", deleteBtn.title);
    deleteBtn.innerHTML = `<span class="icon-mono">🗑️</span>`;
    if (isFieldDisabled) deleteBtn.disabled = true;

    controlsContainer.appendChild(translateBtn);
    controlsContainer.appendChild(deleteBtn);

    toolbar.appendChild(leftGroup);
    toolbar.appendChild(controlsContainer);

    inputEl.parentNode.insertBefore(toolbar, inputEl);

    const syncHiddenJson = () => {
      if (hiddenInput) {
        hiddenInput.value = JSON.stringify(variants);
      }
    };

    inputEl.addEventListener("aimo:i18n-reload", () => {
      if (hiddenInput && hiddenInput.value) {
        try {
          const reloaded = JSON.parse(hiddenInput.value) || {};
          Object.keys(variants).forEach((k) => delete variants[k]);
          Object.keys(reloaded).forEach((code) => {
            const item = reloaded[code];
            if (item && typeof item === "object") {
              const txt = String(item.content ?? item.text ?? "");
              const out = Boolean(item.is_outdated ?? item.outdated ?? false);
              variants[code] = { content: txt, text: txt, is_outdated: out, outdated: out };
            }
          });
        } catch (_) {}
      }
      activeLang = originLang || "en";
      isProvidingTranslation = false;
      dirtyInCurrentTab = false;
      inputEl.dataset.i18nActiveLang = activeLang;
      renderFlags();
    });

    const hasContentFor = (code) =>
      Boolean(variants[code] && typeof variants[code].content === "string" && variants[code].content.trim() !== "");

    const updateDeleteBtnState = () => {
      const canDelete =
        !isFieldDisabled &&
        Boolean(activeLang) &&
        activeLang !== "en" &&
        (hasContentFor(activeLang) || inputEl.value.trim() !== "");
      deleteBtn.disabled = !canDelete;
      deleteBtn.style.display = canDelete ? "" : "none";
    };

    const renderFlags = () => {
      updateDeleteBtnState();
      flagsContainer.innerHTML = "";
      const liveList = AIMO_LANGUAGES.filter(
        (m) => hasContentFor(m.code) && !variants[m.code]?.is_outdated
      );
      const outdatedList = AIMO_LANGUAGES.filter(
        (m) => hasContentFor(m.code) && Boolean(variants[m.code]?.is_outdated)
      );
      const missingList = AIMO_LANGUAGES.filter((m) => !hasContentFor(m.code));
      const sortedLanguages = [...liveList, ...outdatedList, ...missingList];

      sortedLanguages.forEach((meta) => {
        const hasText = hasContentFor(meta.code);
        const entry = variants[meta.code] || { content: "", is_outdated: false };
        const flagBtn = document.createElement("button");
        flagBtn.type = "button";
        flagBtn.className = "i18n-flag-btn";
        if (isFieldDisabled) flagBtn.disabled = true;
        if (!hasText) {
          flagBtn.classList.add("missing");
        }
        if (meta.code === activeLang) {
          flagBtn.classList.add("active");
        }
        if (entry.is_outdated) {
          flagBtn.classList.add("outdated");
        }
        flagBtn.textContent = `${meta.flag} ${meta.code.toUpperCase()}`;
        flagBtn.title = !hasText
          ? `${meta.label} — ${window.t ? window.t("Not translated yet (click to enter manually or AI translate)") : "Not translated yet (click to enter manually or AI translate)"}`
          : entry.is_outdated
            ? `${meta.label} — ${window.t ? window.t("Translation may be outdated (click to review)") : "Translation may be outdated (click to review)"}`
            : meta.label;

        flagBtn.addEventListener("click", () => {
          if (activeLang && (inputEl.value.trim() !== "" || variants[activeLang])) {
            const prevOutdated = Boolean(variants[activeLang]?.is_outdated);
            variants[activeLang] = {
              content: inputEl.value,
              text: inputEl.value,
              is_outdated: prevOutdated,
              outdated: prevOutdated,
            };
          }
          activeLang = meta.code;
          isProvidingTranslation = meta.code !== originLang;
          dirtyInCurrentTab = false;
          inputEl.dataset.i18nActiveLang = activeLang;
          inputEl.value = variants[meta.code]?.content || "";
          syncHiddenJson();
          renderFlags();
          if (!hasText) {
            inputEl.focus();
          }
        });
        flagsContainer.appendChild(flagBtn);
      });
    };

    inputEl.addEventListener("input", () => {
      const newVal = inputEl.value;
      if (!activeLang) activeLang = originLang || "en";
      dirtyInCurrentTab = true;

      variants[activeLang] = {
        content: newVal,
        text: newVal,
        is_outdated: false,
        outdated: false,
      };

      if (!isProvidingTranslation) {
        Object.keys(variants).forEach((code) => {
          if (code !== activeLang && variants[code] && variants[code].content.trim() !== "") {
            variants[code].is_outdated = true;
            variants[code].outdated = true;
          }
        });
      }

      syncHiddenJson();
      renderFlags();
    });

    deleteBtn.addEventListener("click", () => {
      if (!activeLang || activeLang === "en") return;
      delete variants[activeLang];
      inputEl.value = "";
      dirtyInCurrentTab = false;
      syncHiddenJson();
      renderFlags();
    });

    translateBtn.addEventListener("click", async () => {
      const targetLang = activeLang || originLang || "en";
      const currentInput = inputEl.value.trim();
      const sourceText = (
        (dirtyInCurrentTab && currentInput)
          ? currentInput
          : (
              variants["en"]?.content ||
              variants[originLang]?.content ||
              (activeLang !== targetLang ? inputEl.value : "") ||
              Object.values(variants).find((v) => v && v.content && v.content.trim())?.content ||
              inputEl.value ||
              ""
            )
      ).trim();
      if (!sourceText) {
        window.showToastWarning("Please enter source text first before translating.");
        return;
      }
      const origHtml = window.setButtonLoading(translateBtn, "Translating...");

      try {
        const resp = await fetch("/api/chat/translate-text", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: sourceText,
            target_language: targetLang,
            entity_type: entityType,
            entity_id: entityId,
            field_name: fieldName,
          }),
        });
        const data = await resp.json();
        if (resp.ok && data.translated_text) {
          variants[targetLang] = {
            content: data.translated_text,
            text: data.translated_text,
            is_outdated: false,
            outdated: false,
          };
          activeLang = targetLang;
          isProvidingTranslation = false;
          dirtyInCurrentTab = false;
          inputEl.dataset.i18nActiveLang = activeLang;
          inputEl.value = data.translated_text;
          syncHiddenJson();
          renderFlags();
        } else {
          window.showToastError(data.error || "Translation failed.", "Translation Error");
        }
      } catch (_) {
        window.showToastError("Failed to connect to translation service.", "Connection Error");
      } finally {
        window.resetButtonLoading(translateBtn, origHtml);
      }
    });

    const parentForm = inputEl.closest("form");
    if (parentForm) {
      parentForm.addEventListener("submit", (e) => {
        if (window.aimoPersonaVisionRunning && parentForm.closest("#persona-manager-modal")) {
          e.preventDefault();
          return;
        }
        if (activeLang && inputEl.value.trim() !== "") {
          const curOutdated = Boolean(variants[activeLang]?.is_outdated);
          variants[activeLang] = {
            content: inputEl.value,
            text: inputEl.value,
            is_outdated: curOutdated,
            outdated: curOutdated,
          };
        }
        // Remove any empty placeholder language entries before saving
        Object.keys(variants).forEach((code) => {
          if (!variants[code] || !variants[code].content || variants[code].content.trim() === "") {
            delete variants[code];
          }
        });
        syncHiddenJson();

        if (variants["en"] && variants["en"].content && variants["en"].content.trim() !== "") {
          inputEl.value = variants["en"].content;
        } else if (
          variants[originLang] &&
          variants[originLang].content &&
          variants[originLang].content.trim() !== ""
        ) {
          inputEl.value = variants[originLang].content;
        } else {
          const firstKey = Object.keys(variants)[0];
          if (firstKey && variants[firstKey]?.content) {
            inputEl.value = variants[firstKey].content;
          }
        }
      });
    }

    inputEl._reloadI18nVariants = (rawJsonStr, newEntityId, fallbackText) => {
      if (typeof newEntityId === "string") {
        entityId = newEntityId;
        inputEl.setAttribute("data-i18n-entity-id", newEntityId);
      }
      Object.keys(variants).forEach((k) => delete variants[k]);
      let parsed = {};
      if (rawJsonStr) {
        try {
          parsed = typeof rawJsonStr === "string" ? JSON.parse(rawJsonStr) : rawJsonStr;
        } catch (_) {
          parsed = {};
        }
      }
      const nextRaw =
        parsed && typeof parsed.variants === "object" && parsed.variants !== null
          ? parsed.variants
          : parsed;
      Object.keys(nextRaw || {}).forEach((code) => {
        const item = nextRaw[code];
        if (item && typeof item === "object") {
          const txt = String(item.content ?? item.text ?? "");
          const out = Boolean(item.is_outdated ?? item.outdated ?? false);
          if (txt.trim() !== "") {
            variants[code] = { content: txt, text: txt, is_outdated: out, outdated: out };
          }
        }
      });

      originLang =
        Object.keys(variants)[0] ||
        (AIMO_LANGUAGES.some((l) => l.code === sysLang) ? sysLang : "de");

      const initTxt = typeof fallbackText === "string" ? fallbackText : inputEl.value || "";
      if (initTxt.trim() && Object.keys(variants).length === 0) {
        variants[originLang] = {
          content: initTxt,
          text: initTxt,
          is_outdated: false,
          outdated: false,
        };
      }

      activeLang = sysLang;
      isProvidingTranslation = activeLang !== originLang;
      inputEl.value = variants[activeLang]?.content ?? (Object.keys(variants).length > 0 ? "" : initTxt);
      syncHiddenJson();
      renderFlags();
    };

    syncHiddenJson();
    renderFlags();
  });
}


  window.initEditorI18nFields = initEditorI18nFields;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initEditorI18nFields);
  } else {
    initEditorI18nFields();
  }
}
