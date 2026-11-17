/**
 * character_creator.js
 * Client logic for the Character Designer in AIMO.
 * Manages KI-Autor generation, vision extraction, dynamic world/location filtering,
 * dialogue example management, lorebook linking, and image cropping.
 * Pure HTML5 approach: context is derived from data-* attributes and DOM elements.
 */

(() => {
  function getFormElement() {
    return document.getElementById("character-main-form");
  }

  function getCharacterContext() {
    const form = getFormElement();
    return {
      characterId: form?.dataset.characterId || null,
      characterName: form?.dataset.characterName || "",
      activePersonaName: form?.dataset.activePersona || "Du",
    };
  }

  // Sprite scroll position preservation
  window.saveSpriteScrollPos = function () {
    try {
      sessionStorage.setItem("aimo_sprite_scroll_y", String(window.scrollY || window.pageYOffset || 0));
    } catch (_) {}
  };

  window.saveSpriteScrollAndSubmit = function (formEl) {
    window.saveSpriteScrollPos();
    if (formEl) formEl.submit();
  };

  function restoreSpriteScroll() {
    try {
      const savedY = sessionStorage.getItem("aimo_sprite_scroll_y");
      if (savedY !== null) {
        sessionStorage.removeItem("aimo_sprite_scroll_y");
        const targetY = parseInt(savedY, 10);
        if (!Number.isNaN(targetY) && targetY > 0) {
          if ("scrollRestoration" in history) {
            history.scrollRestoration = "manual";
          }
          const restoreScroll = () => window.scrollTo({ top: targetY, behavior: "instant" });
          restoreScroll();
          requestAnimationFrame(restoreScroll);
          window.addEventListener("load", restoreScroll, { once: true });
        }
      }
    } catch (_) {}
  }

  function initSparkleAuthor() {
    const btn = document.getElementById("sparkle-improve-btn");
    const textarea = document.getElementById("char-description-textarea");
    const nameInput = document.getElementById("char-name-input");
    const genderSelect = document.querySelector('select[name="gender"]');
    if (!textarea || !btn) return;

    btn.addEventListener("click", async () => {
      btn.classList.add("is-loading");
      btn.disabled = true;
      btn.innerHTML = '<span class="thinking-dots" aria-hidden="true"><span></span><span></span><span></span></span> <span>KI-Autor schreibt</span>';

      const origPlaceholder = textarea.placeholder;
      if (!textarea.value.trim()) {
        textarea.placeholder = "✨ KI-Autor verfasst die Beschreibung";
      }

      try {
        const resp = await fetch("/api/characters/sparkle", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: nameInput ? nameInput.value : "",
            gender: genderSelect ? genderSelect.value : "",
            description: textarea.value,
          }),
        });

        let data = null;
        try {
          data = await resp.json();
        } catch (_) {
          data = null;
        }

        if (resp.ok && data && data.description) {
          textarea.value = data.description;
          textarea.dispatchEvent(new Event("input", { bubbles: true }));
          if (window.showToastSuccess) {
            window.showToastSuccess("Beschreibung erfolgreich generiert.");
          }
        } else {
          const errMsg = (data && data.error)
            || (resp.ok ? "Keine Beschreibung erhalten." : `Serverfehler (${resp.status}): Konnte Beschreibung nicht generieren.`);
          if (window.showToastError) window.showToastError(errMsg); else alert(errMsg);
        }
      } catch (err) {
        const errText = "Verbindungsfehler zum KI-Autor: " + (err.message || err);
        if (window.showToastError) window.showToastError(errText); else alert(errText);
      } finally {
        btn.classList.remove("is-loading");
        btn.disabled = false;
        btn.innerHTML = '<span class="icon-mono">✨</span><span>KI-Autor Optimierung</span>';
        textarea.placeholder = origPlaceholder;
      }
    });
  }

  function initVisionAppearance() {
    const btn = document.getElementById("extract-appearance-btn");
    const textarea = document.getElementById("char-appearance-textarea");
    const fileInput = document.getElementById("primary-portrait-input");
    if (!btn || !textarea) return;

    btn.addEventListener("click", async () => {
      const origHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="icon-sparkle">👁️</span> Analysiere Bild...';

      const ctx = getCharacterContext();

      try {
        let resp;
        if (fileInput && fileInput.files && fileInput.files.length > 0) {
          const fd = new FormData();
          fd.append("primary_portrait", fileInput.files[0]);
          resp = await fetch("/api/characters/extract-appearance", {
            method: "POST",
            body: fd,
          });
        } else if (ctx.characterId) {
          resp = await fetch("/api/characters/extract-appearance", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ character_id: ctx.characterId }),
          });
        } else {
          if (window.showToastWarning) {
            window.showToastWarning("Bitte wähle zuerst ein Porträtbild aus.");
          } else {
            alert("Bitte wähle zuerst ein Porträtbild aus.");
          }
          return;
        }

        let data = null;
        try {
          data = await resp.json();
        } catch (_) {
          data = null;
        }

        if (resp.ok && data && data.appearance) {
          textarea.value = data.appearance;
          textarea.dispatchEvent(new Event("input", { bubbles: true }));
          if (window.showToastSuccess) {
            window.showToastSuccess("Aussehen erfolgreich aus Bild extrahiert.");
          }
        } else {
          const errMsg = (data && data.error)
            || (resp.ok ? "Kein Aussehen extrahiert." : `Serverfehler (${resp.status}): Aussehen konnte nicht extrahiert werden.`);
          if (window.showToastError) window.showToastError(errMsg); else alert(errMsg);
        }
      } catch (err) {
        if (window.showToastError) {
          window.showToastError("Fehler bei der Bildanalyse: " + err);
        } else {
          alert("Fehler bei der Bildanalyse: " + err);
        }
      } finally {
        btn.disabled = false;
        btn.innerHTML = origHtml;
      }
    });
  }

  function initWorldLocationsFilter() {
    const worldSelect = document.getElementById("char-worldinfo-select");
    const container = document.getElementById("worldinfo-locations-container");
    const initialSelect = document.getElementById("char-initial-location-select");
    const preferredSelect = document.getElementById("char-preferred-locations-select");
    const dislikedSelect = document.getElementById("char-disliked-locations-select");

    if (!worldSelect || !container) return;

    // Cache template options once from DOM
    const initialMasterOptions = initialSelect
      ? Array.from(initialSelect.querySelectorAll("option[data-worldinfo-id]"))
      : [];
    const preferredMasterOptions = preferredSelect
      ? Array.from(preferredSelect.querySelectorAll("option[data-worldinfo-id]"))
      : [];
    const dislikedMasterOptions = dislikedSelect
      ? Array.from(dislikedSelect.querySelectorAll("option[data-worldinfo-id]"))
      : [];

    function updateLocationsForWorld(worldId, preserveSelected = true) {
      if (!worldId) {
        container.style.display = "none";
        if (initialSelect) initialSelect.value = "";
        if (preferredSelect) Array.from(preferredSelect.options).forEach(o => { o.selected = false; });
        if (dislikedSelect) Array.from(dislikedSelect.options).forEach(o => { o.selected = false; });
        return;
      }

      container.style.display = "flex";

      const prevInitial = preserveSelected && initialSelect ? initialSelect.value : "";
      const prevPreferred = preserveSelected && preferredSelect
        ? Array.from(preferredSelect.selectedOptions).map(o => o.value)
        : [];
      const prevDisliked = preserveSelected && dislikedSelect
        ? Array.from(dislikedSelect.selectedOptions).map(o => o.value)
        : [];

      if (initialSelect) {
        initialSelect.innerHTML = '<option value="">-- Kein fester Startort --</option>';
        initialMasterOptions
          .filter(opt => opt.dataset.worldinfoId === String(worldId))
          .forEach(opt => {
            const clone = opt.cloneNode(true);
            if (String(clone.value) === String(prevInitial)) clone.selected = true;
            initialSelect.appendChild(clone);
          });
      }

      if (preferredSelect) {
        preferredSelect.innerHTML = "";
        preferredMasterOptions
          .filter(opt => opt.dataset.worldinfoId === String(worldId))
          .forEach(opt => {
            const clone = opt.cloneNode(true);
            if (prevPreferred.includes(String(clone.value))) clone.selected = true;
            preferredSelect.appendChild(clone);
          });
      }

      if (dislikedSelect) {
        dislikedSelect.innerHTML = "";
        dislikedMasterOptions
          .filter(opt => opt.dataset.worldinfoId === String(worldId))
          .forEach(opt => {
            const clone = opt.cloneNode(true);
            if (prevDisliked.includes(String(clone.value))) clone.selected = true;
            dislikedSelect.appendChild(clone);
          });
      }
    }

    worldSelect.addEventListener("change", () => {
      updateLocationsForWorld(worldSelect.value, false);
    });

    if (worldSelect.value) {
      updateLocationsForWorld(worldSelect.value, true);
    }
  }

  function initDialogueManager() {
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
    const genderSelect = document.querySelector('select[name="gender"]');

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
          alert("Bitte gib mindestens einen Trigger oder eine Response ein.");
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
          alert("Bitte gib zuerst im Reiter 'Basis-Info' eine aussagekräftige Charakterbeschreibung ein.");
        }
        return;
      }

      const origHtml = sparkleModalBtn.innerHTML;
      const origTriggerPlaceholder = triggerInput.placeholder;
      const origResponsePlaceholder = responseInput.placeholder;

      sparkleModalBtn.classList.add("is-loading");
      sparkleModalBtn.disabled = true;
      sparkleModalBtn.innerHTML = '<span class="thinking-dots" aria-hidden="true"><span></span><span></span><span></span></span> <span>KI entwirft Dialog</span>';

      if (!triggerInput.value) {
        triggerInput.placeholder = "✨ Analysiere Charakterbeschreibung";
      }
      if (!responseInput.value) {
        responseInput.placeholder = "✨ Formuliere in-character Antwort";
      }

      const userLang = (document.documentElement.lang || "de").slice(0, 2).toLowerCase();
      const payload = {
        name: getCharacterName(),
        gender: genderSelect ? genderSelect.value : "",
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
        sparkleModalBtn.classList.remove("is-loading");
        sparkleModalBtn.disabled = false;
        sparkleModalBtn.innerHTML = '<span class="icon-mono">✨</span><span>Mit KI ausfüllen</span>';
        triggerInput.placeholder = origTriggerPlaceholder;
        responseInput.placeholder = origResponsePlaceholder;
      }
    });
  }

  function initLorebooksManager() {
    const filterInput = document.getElementById("lorebook-filter-input");
    const pickerList = document.getElementById("lorebook-picker-list");
    const linkedList = document.getElementById("linked-lorebooks-list");
    const emptyNotice = document.getElementById("lorebook-empty-notice");

    if (!pickerList || !linkedList) return;

    function updateEmptyNotice() {
      if (emptyNotice) {
        const count = linkedList.querySelectorAll(".lorebook-list-item").length;
        emptyNotice.style.display = count === 0 ? "block" : "none";
      }
    }

    function getAvailableWorldinfos() {
      const worldSelect = document.getElementById("char-worldinfo-select");
      if (!worldSelect) return [];
      return Array.from(worldSelect.querySelectorAll("option"))
        .filter(opt => opt.value)
        .map(opt => ({ id: opt.value, name: opt.textContent.trim() }));
    }

    filterInput?.addEventListener("input", () => {
      const query = filterInput.value.toLowerCase().trim();
      pickerList.querySelectorAll(".lorebook-picker-item").forEach(item => {
        const name = (item.getAttribute("data-name") || "").toLowerCase();
        const desc = (item.getAttribute("data-desc") || "").toLowerCase();
        item.style.display = (name.includes(query) || desc.includes(query)) ? "flex" : "none";
      });
    });

    pickerList.querySelectorAll(".lorebook-picker-item").forEach(item => {
      item.addEventListener("click", () => {
        if (item.classList.contains("already-added")) return;

        const lbId = item.getAttribute("data-id");
        const lbName = item.getAttribute("data-fullname");
        const lbDesc = item.getAttribute("data-desc");

        const row = document.createElement("div");
        row.className = "lorebook-list-item";
        row.setAttribute("data-lorebook-id", lbId);
        row.style.display = "flex";
        row.style.justifyContent = "space-between";
        row.style.alignItems = "center";
        row.style.gap = "1rem";
        row.style.flexWrap = "wrap";

        const hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = "linked_lorebook_ids";
        hidden.value = lbId;
        row.appendChild(hidden);

        const info = document.createElement("div");
        info.style.flex = "1";
        info.style.minWidth = "200px";
        info.innerHTML = `<div style="font-weight: 700; color: var(--gold-accent); font-size: 0.95rem;">${lbName}</div>`
          + (lbDesc ? `<div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.15rem;">${lbDesc}</div>` : "");
        row.appendChild(info);

        const actionsDiv = document.createElement("div");
        actionsDiv.style.display = "flex";
        actionsDiv.style.alignItems = "center";
        actionsDiv.style.gap = "0.65rem";

        let optionsHtml = '<option value="">🌍 Alle Welten (Immer aktiv)</option>';
        getAvailableWorldinfos().forEach(wi => {
          optionsHtml += `<option value="${wi.id}">🌐 Nur in Welt: ${wi.name}</option>`;
        });

        const select = document.createElement("select");
        select.name = `lorebook_world_condition_${lbId}`;
        select.style.fontSize = "0.82rem";
        select.style.padding = "0.35rem 0.6rem";
        select.style.maxWidth = "240px";
        select.title = "Wann soll dieses Lorebook aktiv sein?";
        select.innerHTML = optionsHtml;
        actionsDiv.appendChild(select);

        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "aimo-btn danger remove-lorebook-btn";
        delBtn.title = "Lorebook entkoppeln";
        delBtn.innerHTML = '<span class="icon-mono">🗑️</span>';
        delBtn.addEventListener("click", () => {
          row.remove();
          item.classList.remove("already-added");
          const badge = item.querySelector(".picker-status-badge");
          if (badge) badge.textContent = "+ Hinzufügen";
          updateEmptyNotice();
        });
        actionsDiv.appendChild(delBtn);

        row.appendChild(actionsDiv);
        linkedList.appendChild(row);

        item.classList.add("already-added");
        const statusBadge = item.querySelector(".picker-status-badge");
        if (statusBadge) statusBadge.textContent = "✓ Verknüpft";
        updateEmptyNotice();

        if (window.AimoModals && typeof window.AimoModals.close === "function") {
          window.AimoModals.close("add-lorebook-modal");
        } else {
          document.getElementById("add-lorebook-modal")?.classList.remove("open");
        }
      });
    });

    linkedList.querySelectorAll(".remove-lorebook-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const row = btn.closest(".lorebook-list-item");
        const lbId = btn.getAttribute("data-id");
        if (row) row.remove();
        if (lbId) {
          const pickerItem = pickerList.querySelector(`.lorebook-picker-item[data-id="${lbId}"]`);
          if (pickerItem) {
            pickerItem.classList.remove("already-added");
            const badge = pickerItem.querySelector(".picker-status-badge");
            if (badge) badge.textContent = "+ Hinzufügen";
          }
        }
        updateEmptyNotice();
      });
    });
  }

  function initCropper() {
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

  function init() {
    restoreSpriteScroll();
    initSparkleAuthor();
    initVisionAppearance();
    initWorldLocationsFilter();
    initDialogueManager();
    initLorebooksManager();
    initCropper();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
