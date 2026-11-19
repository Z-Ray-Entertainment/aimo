// Persona Manager Modal, Vision Feature Extraction & Portrait Cropper
window.aimoPersonaVisionRunning = false;

/**
 * Standardized HTML markup for animated thinking dots (Chat bounce style).
 * @returns {string} Standardized HTML string with 3 animated bouncing dots
 */

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
  if (!locked) {
    const deleteBtn = document.getElementById("edit-persona-delete-btn");
    if (deleteBtn && deleteBtn.dataset.inUse === "1") deleteBtn.disabled = true;
    ["new", "edit"].forEach((prefix) => {
      const img = document.getElementById(`${prefix}-persona-preview-img`);
      const openBtn = document.getElementById(`${prefix}-persona-open-crop-btn`);
      if (openBtn && img) openBtn.disabled = !img.getAttribute("src");
    });
  }
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
    window.showToastWarning(window.t("Please select a portrait image first to extract image features."));
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

  const origBtnHtml = window.setButtonLoading(visionBtn, window.t("Analyzing image"));
  window.setPersonaEditorLocked(true);
  if (statusEl) {
    statusEl.style.color = "var(--gold-accent)";
    statusEl.textContent = window.t("⏳ Analyzing image (Save & Close locked)");
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
        statusEl.textContent = "✓ " + window.t("Image features extracted");
      }
    } else {
      const errMsg = data.error || window.t("Image analysis failed.");
      if (statusEl) {
        statusEl.style.color = "#E74C3C";
        statusEl.textContent = `⚠️ ${errMsg}`;
      } else {
        window.showToastError(errMsg, window.t("Image analysis error"));
      }
    }
  } catch (_) {
    if (statusEl) {
      statusEl.style.color = "#E74C3C";
      statusEl.textContent = "⚠️ " + window.t("Connection error during image analysis.");
    } else {
      window.showToastError(window.t("Connection error during image analysis."), window.t("Connection error"));
    }
  } finally {
    window.setPersonaEditorLocked(false);
    window.resetButtonLoading(visionBtn, origBtnHtml);
  }
};

window.personaCropControllers = {};

window.resetPersonaPortraitPreview = function resetPersonaPortraitPreview(prefix, src) {
  const wrap = document.getElementById(`${prefix}-persona-preview-wrap`);
  const img = document.getElementById(`${prefix}-persona-preview-img`);
  const openBtn = document.getElementById(`${prefix}-persona-open-crop-btn`);
  const badge = document.getElementById(`${prefix}-persona-crop-badge`);
  const fileInput = document.getElementById(`${prefix}-persona-portrait`);
  if (fileInput) fileInput.value = "";
  if (badge) badge.style.display = "none";
  if (img) img.src = src || "";
  if (wrap) wrap.style.display = src ? "block" : "none";
  if (openBtn) openBtn.disabled = !src;
};

window.openNewPersonaForm = function openNewPersonaForm() {
  if (window.aimoPersonaVisionRunning) return;
  const editBox = document.getElementById("edit-persona-form-box");
  const newBox = document.getElementById("new-persona-form-box");
  const titleEl = document.getElementById("persona-modal-title");
  const form = document.getElementById("new-persona-form");
  const statusEl = document.getElementById("new-persona-vision-status");
  if (form) form.reset();
  if (statusEl) statusEl.textContent = "";
  window.resetPersonaPortraitPreview("new", "");
  if (titleEl) titleEl.innerHTML = `<span class="icon-mono">👤</span> ${window.t ? window.t("Create New Persona") : "Create New Persona"}`;
  if (editBox) editBox.style.display = "none";
  if (newBox) newBox.style.display = "block";
  window.AimoModals.open("persona-manager-modal");
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
  const portraitUrl = btn.getAttribute("data-persona-portrait-url") || "";
  const inUse = btn.getAttribute("data-persona-in-use") === "1";

  form.action = `/personas/${id}/edit`;
  const idInput = document.getElementById("edit-persona-id");
  const preuploadedInput = document.getElementById("edit-persona-preuploaded-portrait");
  const statusEl = document.getElementById("edit-persona-vision-status");
  const nameInput = document.getElementById("edit-persona-name");
  const genderSelect = document.getElementById("edit-persona-gender");
  const descInput = document.getElementById("edit-persona-description");
  const appInput = document.getElementById("edit-persona-appearance");
  const deleteForm = document.getElementById("edit-persona-delete-form");
  const deleteBtn = document.getElementById("edit-persona-delete-btn");
  const titleEl = document.getElementById("persona-modal-title");

  if (idInput) idInput.value = id;
  if (preuploadedInput) preuploadedInput.value = "";
  if (statusEl) statusEl.textContent = "";
  if (nameInput) nameInput.value = name;
  if (genderSelect) genderSelect.value = gender;
  if (descInput) descInput.value = desc;
  if (appInput) appInput.value = appearance;
  if (deleteForm) deleteForm.action = `/personas/${id}/delete`;
  if (deleteBtn) {
    deleteBtn.dataset.inUse = inUse ? "1" : "0";
    deleteBtn.disabled = inUse;
    deleteBtn.title = inUse
      ? (window.t ? window.t("Used in active chats (deletion protection)") : "Used in active chats (deletion protection)")
      : (window.t ? window.t("Delete persona") : "Delete persona");
    deleteBtn.innerHTML = inUse
      ? `<span class="icon-mono">🔒</span> ${window.t ? window.t("Deletion locked") : "Deletion locked"}`
      : `<span class="icon-mono">🗑️</span> ${window.t ? window.t("Delete") : "Delete"}`;
  }
  window.resetPersonaPortraitPreview("edit", portraitUrl);
  if (titleEl) titleEl.innerHTML = `<span class="icon-mono">👤</span> ${window.t ? window.t("Edit Persona") : "Edit Persona"}`;

  editBox.style.display = "block";
  window.AimoModals.open("persona-manager-modal");
};

document.addEventListener("DOMContentLoaded", () => {
  ["new", "edit"].forEach((prefix) => {
    window.AimoImageCropper?.setup({
      modalId: `persona-${prefix}-crop-modal`,
      fileInputId: `${prefix}-persona-portrait`,
      openBtnId: `${prefix}-persona-open-crop-btn`,
      statusBadgeId: `${prefix}-persona-crop-badge`,
      targets: [
        {
          id: "avatar",
          ratio: 1.0,
          inputElement: document.getElementById(`${prefix}-persona-portrait`),
          previewImgElement: document.getElementById(`${prefix}-persona-preview-img`),
          previewWrapElement: document.getElementById(`${prefix}-persona-preview-wrap`),
          outputFilename: "persona_1_1.png",
        },
      ],
    });
  });
});

