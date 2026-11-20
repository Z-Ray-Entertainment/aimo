import { getCharacterContext } from "./creator_core.js";

export function initDialogueManager() {
  const hiddenInput = document.getElementById("dialogue-examples-json");
  const listContainer = document.getElementById("dialogue-examples-list");
  const emptyNotice = document.getElementById("dialogue-empty-notice");
  const confirmBtn = document.getElementById("confirm-add-dialogue-btn");
  const triggerInput = document.getElementById("modal-dialogue-trigger");
  const responseInput = document.getElementById("modal-dialogue-response");
  const modalTitle = document.getElementById("dialogue-modal-title");
  const openAddBtn = document.querySelector('[data-modal-open="add-dialogue-modal"]');
  const nameInput = document.getElementById("char-name-input");
  const sparkleModalBtn = document.getElementById("sparkle-modal-dialogue-btn");
  const descTextarea = document.getElementById("char-description-textarea");

  if (!hiddenInput || !listContainer) return;

  function getActivePersona() {
    return getCharacterContext().activePersonaName || "Du";
  }

  function getCharacterName() {
    const val = (nameInput ? nameInput.value : "").trim();
    return val || getCharacterContext().characterName || "Charakter";
  }

  function formatDisplayText(raw) {
    if (!raw) return "";
    return raw
      .replace(/\{\{user\}\}/g, getActivePersona())
      .replace(/\{\{char\}\}/g, getCharacterName());
  }

  function updateModalBadges() {
    document.querySelectorAll(".modal-badge-user").forEach(b => {
      b.textContent = getActivePersona();
    });
    document.querySelectorAll(".modal-badge-char").forEach(b => {
      b.textContent = getCharacterName();
    });
  }

  let examples = [];
  let editingIndex = null;

  try {
    examples = JSON.parse(hiddenInput.value || "[]");
  } catch (_) {
    examples = [];
  }

  function syncData() {
    hiddenInput.value = JSON.stringify(examples);
    if (emptyNotice) {
      emptyNotice.style.display = examples.length === 0 ? "block" : "none";
    }
  }

  function openEditModal(idx) {
    if (idx < 0 || idx >= examples.length) return;
    editingIndex = idx;
    if (modalTitle) modalTitle.innerHTML = '<span class="icon-mono">✏️</span> Gesprächsstil bearbeiten';
    if (confirmBtn) confirmBtn.innerHTML = '<span class="icon-mono">💾</span> Speichern';
    if (sparkleModalBtn) {
      sparkleModalBtn.classList.remove("is-loading");
      sparkleModalBtn.disabled = false;
      sparkleModalBtn.innerHTML = '<span class="icon-mono">✨</span><span>Mit KI ausfüllen</span>';
    }
    updateModalBadges();
    triggerInput.value = examples[idx].trigger || "";
    responseInput.value = examples[idx].response || "";

    if (window.AimoModals && typeof window.AimoModals.open === "function") {
      window.AimoModals.open("add-dialogue-modal");
    } else {
      document.getElementById("add-dialogue-modal")?.classList.add("open");
    }
  }

  openAddBtn?.addEventListener("click", () => {
    editingIndex = null;
    if (modalTitle) modalTitle.innerHTML = '<span class="icon-mono">💬</span> Neuen Gesprächsstil hinzufügen';
    if (confirmBtn) confirmBtn.innerHTML = '<span class="icon-mono">➕</span> Hinzufügen';
    if (sparkleModalBtn) {
      sparkleModalBtn.classList.remove("is-loading");
      sparkleModalBtn.disabled = false;
      sparkleModalBtn.innerHTML = '<span class="icon-mono">✨</span><span>Mit KI ausfüllen</span>';
    }
    updateModalBadges();
    triggerInput.value = "";
    responseInput.value = "";
  });

  function renderList() {
    listContainer.innerHTML = "";
    examples.forEach((ex, idx) => {
      const item = document.createElement("div");
      item.className = "dialogue-example-item";
      item.setAttribute("data-index", idx);

      const headerDiv = document.createElement("div");
      headerDiv.className = "dialogue-item-header";

      const indexLabel = document.createElement("span");
      indexLabel.className = "dialogue-index-label";
      indexLabel.innerHTML = `<span class="icon-mono">💬</span> Beispiel ${idx + 1}`;
      headerDiv.appendChild(indexLabel);

      const actionsDiv = document.createElement("div");
      actionsDiv.className = "dialogue-item-actions";

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "aimo-btn edit-dialogue-btn dialogue-action-btn";
      editBtn.title = "Beispiel bearbeiten";
      editBtn.innerHTML = '<span class="icon-mono">✏️</span>';
      editBtn.addEventListener("click", () => openEditModal(idx));

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "aimo-btn danger delete-dialogue-btn dialogue-action-btn";
      delBtn.title = "Beispiel löschen";
      delBtn.innerHTML = '<span class="icon-mono">🗑️</span>';
      delBtn.addEventListener("click", () => {
        examples.splice(idx, 1);
        syncData();
        renderList();
      });

      actionsDiv.appendChild(editBtn);
      actionsDiv.appendChild(delBtn);
      headerDiv.appendChild(actionsDiv);
      item.appendChild(headerDiv);

      const trigDiv = document.createElement("div");
      trigDiv.className = "dialogue-entry-trigger";

      const trigSpan = document.createElement("div");
      trigSpan.className = "dialogue-text";
      trigSpan.textContent = formatDisplayText(ex.trigger || "");
      trigDiv.appendChild(trigSpan);

      const userBadge = document.createElement("span");
      userBadge.className = "role-badge user-badge";
      userBadge.title = "{{user}}";
      userBadge.textContent = getActivePersona();
      trigDiv.appendChild(userBadge);

      item.appendChild(trigDiv);

      const respDiv = document.createElement("div");
      respDiv.className = "dialogue-entry-response";

      const charBadge = document.createElement("span");
      charBadge.className = "role-badge char-badge";
      charBadge.title = "{{char}}";
      charBadge.textContent = getCharacterName();
      respDiv.appendChild(charBadge);

      const respSpan = document.createElement("div");
      respSpan.className = "dialogue-text";
      respSpan.textContent = formatDisplayText(ex.response || "");
      respDiv.appendChild(respSpan);

      item.appendChild(respDiv);
      listContainer.appendChild(item);
    });
    syncData();
  }

  nameInput?.addEventListener("input", () => {
    updateModalBadges();
    renderList();
  });

  renderList();

  confirmBtn?.addEventListener("click", () => {
    const trig = (triggerInput.value || "").trim();
    const resp = (responseInput.value || "").trim();
    if (!trig && !resp) {
      if (window.showToastWarning) {
        window.showToastWarning("Bitte gib mindestens einen Trigger oder eine Response ein.");
      } else {
        alert(window.t("Please enter at least one trigger or response."));
      }
      return;
    }

    if (editingIndex !== null && editingIndex >= 0 && editingIndex < examples.length) {
      examples[editingIndex] = { trigger: trig, response: resp };
    } else {
      examples.push({ trigger: trig, response: resp });
    }

    editingIndex = null;
    syncData();
    renderList();

    triggerInput.value = "";
    responseInput.value = "";

    if (window.AimoModals && typeof window.AimoModals.close === "function") {
      window.AimoModals.close("add-dialogue-modal");
    } else {
      document.getElementById("add-dialogue-modal")?.classList.remove("open");
    }
  });

  sparkleModalBtn?.addEventListener("click", async () => {
    const desc = (descTextarea ? descTextarea.value : "").trim();
    if (!desc || desc.length < 10) {
      if (window.showToastWarning) {
        window.showToastWarning("Bitte gib zuerst im Reiter 'Basis-Info' eine aussagekräftige Charakterbeschreibung ein.");
      } else {
        alert(window.t("Please enter a meaningful character description in the 'Basic Info' tab first."));
      }
      return;
    }

    const origTriggerPlaceholder = triggerInput.placeholder;
    const origResponsePlaceholder = responseInput.placeholder;
    const origBtnHtml = window.setButtonLoading(sparkleModalBtn, window.t("Drafting dialogue"));

    if (!triggerInput.value) {
      triggerInput.placeholder = window.t("✨ Analyzing character description");
    }
    if (!responseInput.value) {
      responseInput.placeholder = window.t("✨ Formulating response");
    }

    const userLang = (document.documentElement.lang || "de").slice(0, 2).toLowerCase();
    const genderInput = document.querySelector('input[name="gender"]:checked') || document.querySelector('select[name="gender"]');
    const payload = {
      name: getCharacterName(),
      gender: genderInput ? genderInput.value : "",
      description: desc,
      language: userLang,
      current_trigger: (triggerInput.value || "").trim(),
      current_response: (responseInput.value || "").trim(),
      existing_examples: examples,
    };

    try {
      const resp = await fetch("/api/characters/sparkle-dialogue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (resp.ok && data) {
        if (data.trigger !== undefined) {
          triggerInput.value = data.trigger;
          triggerInput.dispatchEvent(new Event("input", { bubbles: true }));
        }
        if (data.response !== undefined) {
          responseInput.value = data.response;
          responseInput.dispatchEvent(new Event("input", { bubbles: true }));
        }
        if (window.showToastSuccess) {
          window.showToastSuccess("Dialogbeispiel generiert. Du kannst es nun anpassen und speichern.");
        }
      } else {
        const errMsg = data.error || "Fehler bei der Generierung des Dialogbeispiels.";
        if (window.showToastError) window.showToastError(errMsg); else alert(errMsg);
      }
    } catch (err) {
      const errMsg = "Verbindungsfehler bei der Dialogbeispiel-Generierung.";
      if (window.showToastError) window.showToastError(errMsg); else alert(errMsg);
    } finally {
      window.resetButtonLoading(sparkleModalBtn, '<span class="icon-mono">✨</span><span>Mit KI ausfüllen</span>');
      triggerInput.placeholder = origTriggerPlaceholder;
      responseInput.placeholder = origResponsePlaceholder;
    }
  });
}


export function initCropper() {
  window.AimoImageCropper?.setup({
    modalId: "portrait-crop-modal",
    fileInputId: "primary-portrait-input",
    openBtnId: "open-crop-btn",
    statusBadgeId: "crop-status-badge",
    targets: [
      {
        id: "portrait",
        ratio: 9 / 16,
        inputElement: document.getElementById("primary-portrait-input"),
        previewImgElement: document.getElementById("portrait-preview-img"),
        previewWrapElement: document.getElementById("portrait-preview-wrap"),
        outputFilename: "portrait_9_16.png",
      },
      {
        id: "avatar",
        ratio: 1.0,
        inputElement: document.getElementById("avatar-portrait-input"),
        linkedInputElements: [document.getElementById("card-portrait-input")],
        previewImgElement: document.getElementById("avatar-preview-img"),
        previewWrapElement: document.getElementById("avatar-preview-wrap"),
        outputFilename: "avatar_1_1.png",
      },
    ],
  });
}

export function initImageViewer() {
  if (!window.AimoImageViewer) return;

  const portraitImg = document.getElementById("portrait-preview-img");
  if (portraitImg) {
    portraitImg.addEventListener("click", () => {
      if (portraitImg.src) {
        window.AimoImageViewer.openSingle(portraitImg.src, portraitImg.alt || "Portrait");
      }
    });
  }

  const avatarImg = document.getElementById("avatar-preview-img");
  if (avatarImg) {
    avatarImg.addEventListener("click", () => {
      if (avatarImg.src) {
        window.AimoImageViewer.openSingle(avatarImg.src, avatarImg.alt || "Avatar");
      }
    });
  }

  const galleryGrid = document.getElementById("char-gallery-grid");
  if (galleryGrid) {
    galleryGrid.addEventListener("click", (e) => {
      const target = e.target;
      if (!(target instanceof Element)) return;
      if (target.closest("form, button, a")) return;
      const preview = target.closest(".char-gallery-preview");
      if (!preview) return;

      const previews = Array.from(galleryGrid.querySelectorAll(".char-gallery-preview"));
      const items = [];
      let startIndex = 0;
      for (const el of previews) {
        const src = el.getAttribute("data-viewer-src");
        if (!src) continue;
        if (el === preview) startIndex = items.length;
        items.push({
          src,
          title: el.getAttribute("data-viewer-title") || "",
          subtitle: el.getAttribute("data-viewer-subtitle") || "",
        });
      }
      if (items.length > 0) {
        window.AimoImageViewer.open(items, startIndex);
      }
    });
  }

  const spritesTab = document.getElementById("tab-char-sprites");
  if (spritesTab) {
    spritesTab.addEventListener("click", (e) => {
      const target = e.target;
      if (!(target instanceof Element)) return;
      if (target.closest("form, button, label, a")) return;

      const modalImg = target.closest('[id^="sprite-modal-"] .card-tile img');
      if (modalImg) {
        const modal = modalImg.closest('[id^="sprite-modal-"]');
        const modalImgs = Array.from(modal.querySelectorAll(".card-tile img"));
        const items = modalImgs.map((img) => ({
          src: img.src,
          title: img.getAttribute("alt") || "",
        }));
        const idx = Math.max(0, modalImgs.indexOf(modalImg));
        window.AimoImageViewer.open(items, idx);
        return;
      }

      const spritePreview = target.closest(".char-sprite-preview");
      if (spritePreview) {
        const emotion = spritePreview.getAttribute("data-emotion") || "";
        const modal = emotion ? document.getElementById(`sprite-modal-${emotion}`) : null;
        if (modal) {
          const modalImgs = Array.from(modal.querySelectorAll(".card-tile img"));
          if (modalImgs.length > 0) {
            window.AimoImageViewer.open(
              modalImgs.map((img) => ({ src: img.src, title: img.getAttribute("alt") || "" })),
              0
            );
            return;
          }
        }
        const src = spritePreview.getAttribute("data-viewer-src");
        if (src) {
          window.AimoImageViewer.openSingle(src, spritePreview.getAttribute("data-viewer-title") || emotion);
        }
      }
    });
  }
}

