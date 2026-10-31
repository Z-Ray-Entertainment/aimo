window.aimoPersonaVisionRunning = false;

window.setPersonaEditorLocked = function setPersonaEditorLocked(locked) {
  window.aimoPersonaVisionRunning = Boolean(locked);
  const modal = document.getElementById("persona-manager-modal");
  if (!modal) return;
  if (locked) {
    modal.setAttribute("data-locked", "1");
  } else {
    modal.removeAttribute("data-locked");
  }
  modal.querySelectorAll("[data-persona-lockable='1']").forEach((el) => {
    el.disabled = Boolean(locked);
  });
};

window.extractPersonaVisionFeatures = async function extractPersonaVisionFeatures(mode) {
  if (window.aimoPersonaVisionRunning) return;

  const isEdit = mode === "edit";
  const fileInput = document.getElementById(isEdit ? "edit-persona-portrait" : "new-persona-portrait");
  const preuploadedInput = document.getElementById(
    isEdit ? "edit-persona-preuploaded-portrait" : "new-persona-preuploaded-portrait"
  );
  const personaIdInput = document.getElementById("edit-persona-id");
  const appInput = document.getElementById(isEdit ? "edit-persona-appearance" : "new-persona-appearance");
  const visionBtn = document.getElementById(isEdit ? "edit-persona-vision-btn" : "new-persona-vision-btn");
  const statusEl = document.getElementById(isEdit ? "edit-persona-vision-status" : "new-persona-vision-status");

  const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
  const hasPreuploaded = preuploadedInput && preuploadedInput.value.trim() !== "";
  const hasPersonaId = isEdit && personaIdInput && personaIdInput.value.trim() !== "";

  if (!hasFile && !hasPreuploaded && !hasPersonaId) {
    alert("Bitte wähle zuerst ein Porträtbild aus, um die Bild-Features zu extrahieren.");
    return;
  }

  const formData = new FormData();
  if (hasFile) {
    formData.append("portrait", fileInput.files[0]);
  }
  if (hasPreuploaded) {
    formData.append("preuploaded_portrait_path", preuploadedInput.value.trim());
  }
  if (hasPersonaId) {
    formData.append("persona_id", personaIdInput.value.trim());
  }

  const origBtnHtml = visionBtn ? visionBtn.innerHTML : "";
  window.setPersonaEditorLocked(true);
  if (visionBtn) {
    visionBtn.textContent = "⏳ Analysiere Bild...";
  }
  if (statusEl) {
    statusEl.style.color = "var(--gold-accent)";
    statusEl.textContent = "⏳ Bildanalyse läuft… (Speichern & Schließen gesperrt)";
  }

  try {
    const resp = await fetch("/api/personas/analyze-portrait", {
      method: "POST",
      body: formData,
    });
    const data = await resp.json();
    if (resp.ok && data.appearance) {
      if (data.portrait_path && preuploadedInput) {
        preuploadedInput.value = data.portrait_path;
      }
      if (appInput) {
        appInput.value = data.appearance;
        appInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
      if (statusEl) {
        statusEl.style.color = "#58D68D";
        statusEl.textContent = "✓ Bild-Features extrahiert";
      }
    } else {
      const errMsg = data.error || "Bildanalyse fehlgeschlagen.";
      if (statusEl) {
        statusEl.style.color = "#E74C3C";
        statusEl.textContent = `⚠️ ${errMsg}`;
      } else {
        alert(errMsg);
      }
    }
  } catch (_) {
    if (statusEl) {
      statusEl.style.color = "#E74C3C";
      statusEl.textContent = "⚠️ Verbindungsfehler bei der Bildanalyse.";
    } else {
      alert("Verbindungsfehler bei der Bildanalyse.");
    }
  } finally {
    window.setPersonaEditorLocked(false);
    if (visionBtn && origBtnHtml) {
      visionBtn.innerHTML = origBtnHtml;
    }
  }
};

window.openNewPersonaForm = function openNewPersonaForm() {
  if (window.aimoPersonaVisionRunning) return;
  const editBox = document.getElementById("edit-persona-form-box");
  const newBox = document.getElementById("new-persona-form-box");
  const statusEl = document.getElementById("new-persona-vision-status");
  if (statusEl) statusEl.textContent = "";
  if (editBox) editBox.style.display = "none";
  if (newBox) {
    newBox.style.display = "block";
    newBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
};

window.openEditPersonaFromBtn = function openEditPersonaFromBtn(btn) {
  if (!btn || window.aimoPersonaVisionRunning) return;
  const newBox = document.getElementById("new-persona-form-box");
  const editBox = document.getElementById("edit-persona-form-box");
  const form = document.getElementById("edit-persona-form");
  if (!editBox || !form) return;

  if (newBox) newBox.style.display = "none";

  const id = btn.getAttribute("data-persona-id") || "";
  const name = btn.getAttribute("data-persona-name") || "";
  const gender = btn.getAttribute("data-persona-gender") || "non-binary";
  const desc = btn.getAttribute("data-persona-description") || "";
  const appearance = btn.getAttribute("data-persona-appearance") || "";
  const i18nDesc = btn.getAttribute("data-persona-i18n-description") || "{}";
  const i18nApp = btn.getAttribute("data-persona-i18n-appearance") || "{}";
  const isDefault = btn.getAttribute("data-persona-default") === "1";

  form.action = `/personas/${id}/edit`;
  const idInput = document.getElementById("edit-persona-id");
  const preuploadedInput = document.getElementById("edit-persona-preuploaded-portrait");
  const portraitInput = document.getElementById("edit-persona-portrait");
  const statusEl = document.getElementById("edit-persona-vision-status");
  const nameInput = document.getElementById("edit-persona-name");
  const genderSelect = document.getElementById("edit-persona-gender");
  const descInput = document.getElementById("edit-persona-description");
  const appInput = document.getElementById("edit-persona-appearance");
  const defCheck = document.getElementById("edit-persona-default");

  if (idInput) idInput.value = id;
  if (preuploadedInput) preuploadedInput.value = "";
  if (portraitInput) portraitInput.value = "";
  if (statusEl) statusEl.textContent = "";
  if (nameInput) nameInput.value = name;
  if (genderSelect) genderSelect.value = gender;
  if (descInput) {
    descInput.value = desc;
    if (typeof descInput._reloadI18nVariants === "function") {
      descInput._reloadI18nVariants(i18nDesc, id, desc);
    }
  }
  if (appInput) {
    appInput.value = appearance;
    if (typeof appInput._reloadI18nVariants === "function") {
      appInput._reloadI18nVariants(i18nApp, id, appearance);
    }
  }
  if (defCheck) defCheck.checked = isDefault;

  editBox.style.display = "block";
  editBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
};

window.showAimoToast = function showAimoToast(notif) {
  const container = document.getElementById("aimo-toast-container");
  if (!container || !notif) return;

  const toast = document.createElement("div");
  toast.className = "aimo-toast wood-frame";

  const portraitUrl = notif.character_portrait ? `/uploads/${notif.character_portrait}` : "/static/img/cover.svg";
  const rawPreview = String(notif.localized_content || "").replace(/\s+/g, " ").trim();
  const preview = rawPreview.length > 110 ? `${rawPreview.slice(0, 110)}…` : rawPreview;

  toast.innerHTML = `
    <img src="${portraitUrl}" alt="" class="aimo-toast-avatar" onerror="this.src='/static/img/cover.svg'">
    <div class="aimo-toast-body">
      <div class="aimo-toast-title">💬 ${notif.character_name || "Charakter"} hat geantwortet</div>
      <div class="aimo-toast-preview"></div>
      <div class="aimo-toast-actions">
        <a href="/chat/session/${notif.session_id}" class="btn" style="padding: 0.25rem 0.65rem; font-size: 0.78rem;">Zum Chat →</a>
      </div>
    </div>
    <button type="button" class="aimo-toast-close" title="Schließen">✕</button>
  `;

  const previewEl = toast.querySelector(".aimo-toast-preview");
  if (previewEl) previewEl.textContent = preview;

  const removeToast = () => {
    toast.classList.add("closing");
    setTimeout(() => toast.remove(), 220);
  };

  toast.querySelector(".aimo-toast-close")?.addEventListener("click", removeToast);
  container.appendChild(toast);

  setTimeout(removeToast, 9000);
};

const AIMO_LANGUAGES = [
  { code: "de", flag: "🇩🇪", label: "Deutsch" },
  { code: "en", flag: "🇬🇧", label: "English" },
  { code: "fr", flag: "🇫🇷", label: "Français" },
  { code: "es", flag: "🇪🇸", label: "Español" },
  { code: "it", flag: "🇮🇹", label: "Italiano" },
  { code: "ja", flag: "🇯🇵", label: "日本語" },
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

    const rawSysLang = (navigator.language || "de").slice(0, 2).toLowerCase();
    const sysLang = AIMO_LANGUAGES.some((l) => l.code === rawSysLang) ? rawSysLang : "de";

    let originLang =
      Object.keys(variants)[0] ||
      (AIMO_LANGUAGES.some((l) => l.code === sysLang) ? sysLang : "de");

    const initialText = inputEl.value || "";
    if (initialText.trim() && Object.keys(variants).length === 0) {
      variants[originLang] = {
        content: initialText,
        text: initialText,
        is_outdated: false,
        outdated: false,
      };
    }

    let activeLang = variants[originLang]
      ? originLang
      : Object.keys(variants)[0] || originLang;

    if (variants[activeLang] && typeof variants[activeLang].content === "string") {
      inputEl.value = variants[activeLang].content;
    }

    // Track whether the user is currently providing/fixing a translation so we don't mark the origin language outdated while they type a new translation
    let isProvidingTranslation = false;

    const toolbar = document.createElement("div");
    toolbar.className = "i18n-toolbar";

    const leftGroup = document.createElement("div");
    leftGroup.className = "i18n-left-group";

    // 1. Selector for the initial/origin language ("Sprache der Ersteingabe")
    const originWrap = document.createElement("div");
    originWrap.className = "i18n-origin-wrap";
    const originLabel = document.createElement("span");
    originLabel.className = "i18n-mini-label";
    originLabel.textContent = "Erstsprache:";
    const originSelect = document.createElement("select");
    originSelect.className = "i18n-lang-select i18n-origin-select";
    originSelect.title = "Sprache angeben, in der dieser Text zuerst verfasst wurde";
    AIMO_LANGUAGES.forEach((l) => {
      const opt = document.createElement("option");
      opt.value = l.code;
      opt.textContent = `${l.flag} ${l.label}`;
      if (l.code === originLang) opt.selected = true;
      originSelect.appendChild(opt);
    });
    originWrap.appendChild(originLabel);
    originWrap.appendChild(originSelect);

    // 2. Country Flags Container
    const flagsContainer = document.createElement("div");
    flagsContainer.className = "i18n-flags-list";

    leftGroup.appendChild(originWrap);
    leftGroup.appendChild(flagsContainer);

    // 3. Target language selector + Manual translation button + AI Translate button
    const controlsContainer = document.createElement("div");
    controlsContainer.className = "i18n-translate-controls";

    const langSelect = document.createElement("select");
    langSelect.className = "i18n-lang-select";
    langSelect.title = "Zielsprache für eigene oder KI-Übersetzung wählen";

    const updateDefaultTargetOption = () => {
      const preferredTarget = originLang === "de" ? "en" : "de";
      langSelect.value = preferredTarget;
    };

    AIMO_LANGUAGES.forEach((l) => {
      const opt = document.createElement("option");
      opt.value = l.code;
      opt.textContent = `${l.flag} ${l.label}`;
      langSelect.appendChild(opt);
    });
    updateDefaultTargetOption();

    const manualBtn = document.createElement("button");
    manualBtn.type = "button";
    manualBtn.className = "btn i18n-translate-btn";
    manualBtn.title = "Gewählte Sprache öffnen und selbst eine Übersetzung eingeben";
    manualBtn.innerHTML = `<span class="icon-mono">✍️</span> Selbst übersetzen`;

    const translateBtn = document.createElement("button");
    translateBtn.type = "button";
    translateBtn.className = "btn i18n-translate-btn";
    translateBtn.title = "Aktuellen Text automatisch per KI in die gewählte Sprache übersetzen";
    translateBtn.innerHTML = `<span class="icon-mono">🌐</span> KI-Übersetzen`;

    controlsContainer.appendChild(langSelect);
    controlsContainer.appendChild(manualBtn);
    controlsContainer.appendChild(translateBtn);

    toolbar.appendChild(leftGroup);
    toolbar.appendChild(controlsContainer);

    inputEl.parentNode.insertBefore(toolbar, inputEl);

    const syncHiddenJson = () => {
      if (hiddenInput) {
        hiddenInput.value = JSON.stringify(variants);
      }
    };

    const renderFlags = () => {
      flagsContainer.innerHTML = "";
      const availableCodes = Object.keys(variants).filter(
        (code) =>
          variants[code] &&
          ((typeof variants[code].content === "string" && variants[code].content.trim() !== "") ||
            code === activeLang)
      );

      if (availableCodes.length === 0) {
        const hint = document.createElement("span");
        hint.className = "i18n-flags-empty";
        hint.textContent = "Noch keine Sprachversionen";
        flagsContainer.appendChild(hint);
        return;
      }

      AIMO_LANGUAGES.forEach((meta) => {
        if (!availableCodes.includes(meta.code)) return;
        const entry = variants[meta.code] || { content: "", is_outdated: false };
        const flagBtn = document.createElement("button");
        flagBtn.type = "button";
        flagBtn.className = "i18n-flag-btn";
        if (meta.code === activeLang) {
          flagBtn.classList.add("active");
        }
        if (entry.is_outdated) {
          flagBtn.classList.add("outdated");
        }
        const isOrigin = meta.code === originLang;
        flagBtn.textContent = `${meta.flag} ${meta.code.toUpperCase()}${isOrigin ? " ★" : ""}`;
        flagBtn.title = entry.is_outdated
          ? `${meta.label} — Übersetzung möglicherweise veraltet (Klicken zum Prüfen/Nachbearbeiten)`
          : `${meta.label}${isOrigin ? " (Erstsprache)" : ""} im Editor anzeigen`;

        flagBtn.addEventListener("click", () => {
          // Save current text before switching
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
          // If clicking an outdated flag or non-origin translation to fix it, allow updating it without marking origin outdated
          isProvidingTranslation = Boolean(variants[meta.code]?.is_outdated);
          inputEl.value = variants[meta.code]?.content || "";
          syncHiddenJson();
          renderFlags();
        });
        flagsContainer.appendChild(flagBtn);
      });
    };

    // Changing the initial/origin language ("Erstsprache")
    originSelect.addEventListener("change", () => {
      const newOrigin = originSelect.value;
      const oldOrigin = originLang;
      if (newOrigin === oldOrigin) return;

      const currentText = inputEl.value;
      const existingNonEmpty = Object.keys(variants).filter(
        (c) => variants[c] && variants[c].content && variants[c].content.trim() !== ""
      );

      // If only the initial language existed (or newOrigin doesn't exist yet and activeLang was oldOrigin), reassign the initial text to newOrigin
      if (
        !variants[newOrigin] ||
        !variants[newOrigin].content ||
        variants[newOrigin].content.trim() === ""
      ) {
        const textToMove =
          (activeLang === oldOrigin ? currentText : variants[oldOrigin]?.content) || currentText;
        if (existingNonEmpty.length <= 1 && variants[oldOrigin]) {
          delete variants[oldOrigin];
        }
        if (textToMove) {
          variants[newOrigin] = {
            content: textToMove,
            text: textToMove,
            is_outdated: false,
            outdated: false,
          };
        }
        originLang = newOrigin;
        activeLang = newOrigin;
        inputEl.value = variants[newOrigin]?.content || currentText;
      } else {
        originLang = newOrigin;
        activeLang = newOrigin;
        inputEl.value = variants[newOrigin].content;
      }

      isProvidingTranslation = false;
      updateDefaultTargetOption();
      syncHiddenJson();
      renderFlags();
    });

    // Clicking "✍️ Selbst übersetzen" to provide a manual translation in the selected language
    manualBtn.addEventListener("click", () => {
      // Save current text under activeLang first
      if (activeLang && inputEl.value.trim() !== "") {
        const wasOutdated = Boolean(variants[activeLang]?.is_outdated);
        variants[activeLang] = {
          content: inputEl.value,
          text: inputEl.value,
          is_outdated: wasOutdated,
          outdated: wasOutdated,
        };
      }

      const targetLang = langSelect.value;
      if (!variants[targetLang]) {
        variants[targetLang] = {
          content: "",
          text: "",
          is_outdated: false,
          outdated: false,
        };
      } else {
        variants[targetLang].is_outdated = false;
        variants[targetLang].outdated = false;
      }

      activeLang = targetLang;
      isProvidingTranslation = true;
      inputEl.value = variants[targetLang].content || "";
      syncHiddenJson();
      renderFlags();
      inputEl.focus();
    });

    inputEl.addEventListener("input", () => {
      const newVal = inputEl.value;
      if (!activeLang) activeLang = originLang || "de";

      variants[activeLang] = {
        content: newVal,
        text: newVal,
        is_outdated: false,
        outdated: false,
      };

      // If the user is modifying an existing text (not typing a fresh manual translation), mark all other language flags as outdated (orange border)
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

    translateBtn.addEventListener("click", async () => {
      const sourceText = (inputEl.value || variants[originLang]?.content || "").trim();
      if (!sourceText) {
        alert("Bitte zuerst einen Text eingeben, der übersetzt werden soll.");
        return;
      }
      const targetLang = langSelect.value;
      const origHtml = translateBtn.innerHTML;
      translateBtn.disabled = true;
      translateBtn.textContent = "⏳ Übersetze...";

      try {
        if (!variants[activeLang] || !variants[activeLang].content) {
          variants[activeLang] = {
            content: sourceText,
            text: sourceText,
            is_outdated: false,
            outdated: false,
          };
        }
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
          inputEl.value = data.translated_text;
          syncHiddenJson();
          renderFlags();
        } else {
          alert(data.error || "Übersetzung fehlgeschlagen.");
        }
      } catch (_) {
        alert("Fehler bei der Verbindung zum Übersetzungsdienst.");
      } finally {
        translateBtn.disabled = false;
        translateBtn.innerHTML = origHtml;
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

      activeLang = variants[originLang]
        ? originLang
        : Object.keys(variants)[0] || originLang;
      isProvidingTranslation = false;
      originSelect.value = originLang;
      updateDefaultTargetOption();
      inputEl.value = variants[activeLang]?.content ?? initTxt;
      syncHiddenJson();
      renderFlags();
    };

    syncHiddenJson();
    renderFlags();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  try {
    const sysLang = (navigator.language || "de").slice(0, 2).toLowerCase();
    document.cookie = `aimo_sys_lang=${encodeURIComponent(sysLang)}; path=/; max-age=31536000; SameSite=Lax`;
  } catch (_) {}

  initEditorI18nFields();

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
      if (targetId === "tab-char-sprites" || targetId === "tab-char-info") {
        const url = new URL(window.location.href);
        url.searchParams.set("tab", targetId === "tab-char-sprites" ? "sprites" : "info");
        window.history.replaceState({}, "", url.toString());
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

  // Background AI Reply Notification Poller (On-Site Toast when user is NOT in that chat)
  if (document.querySelector(".persona-avatar-btn")) {
    const pollNotifications = async () => {
      try {
        const chatList = document.getElementById("chat-messages-list");
        const chatPane = document.getElementById("chat-pane-messages");
        const isViewingChat =
          chatList && chatPane && chatPane.classList.contains("active") && !document.hidden;
        const activeSessionId = isViewingChat ? chatList.getAttribute("data-session-id") || "" : "";

        const resp = await fetch(
          `/api/chat/notifications?active_session_id=${encodeURIComponent(activeSessionId)}`
        );
        if (!resp.ok) return;
        const data = await resp.json();
        if (Array.isArray(data.notifications)) {
          data.notifications.forEach((n) => window.showAimoToast(n));
        }
      } catch (_) {
        // Ignore transient network errors
      }
    };

    setInterval(pollNotifications, 2500);
    setTimeout(pollNotifications, 600);
  }
});
