document.addEventListener("DOMContentLoaded", () => {
  // 1. Setup 1:1 Cover Cropper
  window.AimoImageCropper?.setup({
    modalId: "worldinfo-cover-crop-modal",
    fileInputId: "worldinfo-cover-input",
    openBtnId: "open-worldinfo-crop-btn",
    statusBadgeId: "worldinfo-cover-crop-badge",
    targets: [
      {
        id: "cover",
        ratio: 1.0,
        inputElement: document.getElementById("worldinfo-cover-input"),
        previewImgElement: document.getElementById("worldinfo-cover-preview-img"),
        previewWrapElement: document.getElementById("worldinfo-cover-preview-wrap"),
        outputFilename: "cover_1_1.png",
      },
    ],
    onApplied(results) {
      const placeholder = document.getElementById("worldinfo-cover-placeholder-icon");
      if (placeholder) placeholder.style.display = "none";
      const img = document.getElementById("worldinfo-cover-preview-img");
      if (img) img.style.display = "block";
    },
  });

  // 1b. Setup 16:9 World Backdrop live preview & removal
  const wiBackdropInput = document.getElementById("worldinfo-backdrop-input");
  const wiBackdropPreview = document.getElementById("worldinfo-backdrop-preview");
  const wiBackdropPlaceholder = document.getElementById("worldinfo-backdrop-placeholder");
  const wiRemoveBackdropBtn = document.getElementById("worldinfo-remove-backdrop-btn");
  const wiRemoveBackdropInput = document.getElementById("worldinfo-remove-backdrop-input");

  if (wiBackdropInput && wiBackdropPreview) {
    wiBackdropInput.addEventListener("change", () => {
      const file = wiBackdropInput.files?.[0];
      if (!file) return;
      if (wiRemoveBackdropInput) wiRemoveBackdropInput.value = "0";
      const reader = new FileReader();
      reader.onload = (e) => {
        if (e.target?.result) {
          wiBackdropPreview.style.backgroundImage = `url('${e.target.result}')`;
          if (wiBackdropPlaceholder) wiBackdropPlaceholder.style.display = "none";
          if (wiRemoveBackdropBtn) wiRemoveBackdropBtn.style.display = "inline-flex";
        }
      };
      reader.readAsDataURL(file);
    });
  }

  if (wiRemoveBackdropBtn && wiBackdropPreview) {
    wiRemoveBackdropBtn.addEventListener("click", () => {
      if (wiRemoveBackdropInput) wiRemoveBackdropInput.value = "1";
      if (wiBackdropInput) wiBackdropInput.value = "";
      wiBackdropPreview.style.backgroundImage = "";
      if (wiBackdropPlaceholder) wiBackdropPlaceholder.style.display = "";
      wiRemoveBackdropBtn.style.display = "none";
    });
  }

  // Enable / disable new location image analyze button on file pick
  const newLocFileInput = document.getElementById("new-loc-bg-input");
  const newLocAnalyzeBtn = document.getElementById("new-loc-analyze-btn");
  if (newLocFileInput && newLocAnalyzeBtn) {
    newLocFileInput.addEventListener("change", () => {
      newLocAnalyzeBtn.disabled = !newLocFileInput.files || !newLocFileInput.files[0];
    });
  }

  // 2. On-Demand Location Background Image Recognition (New Location)
  newLocAnalyzeBtn?.addEventListener("click", async () => {
    const file = newLocFileInput?.files?.[0];
    if (!file) return;

    const statusEl = document.getElementById("new-loc-analyze-status");
    window.setButtonLoading(newLocAnalyzeBtn, window.t("Analyzing image"));
    if (statusEl) statusEl.textContent = window.t("Analyzing image");

    const formData = new FormData();
    formData.append("background", file);

    try {
      const resp = await fetch("/api/worldinfo/locations/analyze-bg", {
        method: "POST",
        body: formData,
      });
      const data = await resp.json();
      if (resp.ok && data.vision_alt_text) {
        document.getElementById("new-loc-bg-path").value = data.background_image_path || "";
        document.getElementById("new-loc-vision-alt").value = data.vision_alt_text;
        const descEl = document.getElementById("new-loc-desc");
        if (descEl) {
          descEl.value = descEl.value.trim()
            ? `${descEl.value.trim()}\n\n${data.vision_alt_text}`
            : data.vision_alt_text;
        }
        if (statusEl) {
          statusEl.style.color = "#4CAF50";
          statusEl.textContent = "✓ Bildbeschreibung eingefügt";
        }
      } else {
        if (statusEl) {
          statusEl.style.color = "#E57373";
          statusEl.textContent = data.error || "Fehler bei der Analyse";
        }
      }
    } catch (err) {
      if (statusEl) {
        statusEl.style.color = "#E57373";
        statusEl.textContent = "Netzwerkfehler";
      }
    } finally {
      window.resetButtonLoading(newLocAnalyzeBtn, '<span class="icon-mono">🔄</span> Erneut analysieren');
    }
  });

  // 3. On-Demand Location Background Image Recognition (Edit Location Modals)
  document.querySelectorAll(".edit-loc-analyze-btn").forEach((btn) => {
    const locId = btn.getAttribute("data-loc-id");
    const inputId = btn.getAttribute("data-input-id");
    const fileInputEl = document.getElementById(inputId);

    if (fileInputEl) {
      fileInputEl.addEventListener("change", () => {
        if (fileInputEl.files && fileInputEl.files[0]) {
          btn.disabled = false;
        }
      });
    }

    btn.addEventListener("click", async () => {
      const pathId = btn.getAttribute("data-path-id");
      const altId = btn.getAttribute("data-alt-id");
      const descId = btn.getAttribute("data-desc-id");
      const statusId = btn.getAttribute("data-status-id");

      const file = fileInputEl?.files?.[0];
      const existingPath = document.getElementById(pathId)?.value || "";
      const statusEl = document.getElementById(statusId);

      window.setButtonLoading(btn, window.t("Analyzing image"));
      if (statusEl) statusEl.textContent = window.t("Analyzing image");

      const formData = new FormData();
      if (file) {
        formData.append("background", file);
      } else if (existingPath) {
        formData.append("background_image_path", existingPath);
      } else {
        window.resetButtonLoading(btn, '<span class="icon-mono">👁️</span> Bild analysieren &amp; beschreiben');
        if (statusEl) statusEl.textContent = "Kein Bild gewählt";
        return;
      }

      try {
        const resp = await fetch("/api/worldinfo/locations/analyze-bg", {
          method: "POST",
          body: formData,
        });
        const data = await resp.json();
        if (resp.ok && data.vision_alt_text) {
          if (data.background_image_path && document.getElementById(pathId)) {
            document.getElementById(pathId).value = data.background_image_path;
          }
          if (document.getElementById(altId)) {
            document.getElementById(altId).value = data.vision_alt_text;
          }
          const descEl = document.getElementById(descId);
          if (descEl) {
            descEl.value = descEl.value.trim()
              ? `${descEl.value.trim()}\n\n${data.vision_alt_text}`
              : data.vision_alt_text;
          }
          if (statusEl) {
            statusEl.style.color = "#4CAF50";
            statusEl.textContent = "✓ Bildbeschreibung eingefügt";
          }
        } else {
          if (statusEl) {
            statusEl.style.color = "#E57373";
            statusEl.textContent = data.error || "Fehler bei der Analyse";
          }
        }
      } catch (err) {
        if (statusEl) {
          statusEl.style.color = "#E57373";
          statusEl.textContent = "Netzwerkfehler";
        }
      } finally {
        window.resetButtonLoading(btn, '<span class="icon-mono">🔄</span> Erneut analysieren');
      }
    });
  });

  // 4. On-Demand LLM Tag Extraction from Location Description
  document.querySelectorAll(".extract-tags-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const descId = btn.getAttribute("data-desc-id");
      const tagsId = btn.getAttribute("data-tags-id");
      const statusId = btn.getAttribute("data-status-id");

      const descEl = document.getElementById(descId);
      const tagsEl = document.getElementById(tagsId);
      const statusEl = document.getElementById(statusId);

      const description = descEl ? descEl.value.trim() : "";
      if (!description) {
        if (statusEl) {
          statusEl.style.display = "inline-block";
          statusEl.style.color = "#E57373";
          statusEl.textContent = "Bitte zuerst eine Ortsbeschreibung eingeben";
        }
        return;
      }

      window.setButtonLoading(btn, "Extrahiere Tags");
      if (statusEl) {
        statusEl.style.display = "inline-block";
        statusEl.style.color = "var(--text-muted)";
        statusEl.textContent = "Extrahiere Tags";
      }

      try {
        const resp = await fetch("/api/worldinfo/locations/extract-tags", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ description }),
        });
        const data = await resp.json();
        if (resp.ok && data.tags_string) {
          if (tagsEl) {
            tagsEl.value = tagsEl.value.trim()
              ? `${tagsEl.value.trim()}, ${data.tags_string}`
              : data.tags_string;
          }
          if (statusEl) {
            statusEl.style.color = "#4CAF50";
            statusEl.textContent = `✓ ${data.tags.length} Tags übernommen`;
          }
        } else {
          if (statusEl) {
            statusEl.style.color = "#E57373";
            statusEl.textContent = data.error || "Keine Tags extrahiert";
          }
        }
      } catch (err) {
        if (statusEl) {
          statusEl.style.color = "#E57373";
          statusEl.textContent = "Netzwerkfehler";
        }
      } finally {
        window.resetButtonLoading(btn, '<span class="icon-mono">🏷️</span> Tags extrahieren');
      }
    });
  });

  if (window.AimoImageViewer) {
    const wiCoverImg = document.getElementById("worldinfo-cover-preview-img");
    if (wiCoverImg) {
      wiCoverImg.addEventListener("click", () => {
        if (wiCoverImg.src && wiCoverImg.style.display !== "none") {
          window.AimoImageViewer.openSingle(wiCoverImg.src, wiCoverImg.alt || "Cover");
        }
      });
    }

    if (wiBackdropPreview) {
      wiBackdropPreview.addEventListener("click", () => {
        const bg = wiBackdropPreview.style.backgroundImage || "";
        const match = bg.match(/^url\(["']?(.+?)["']?\)$/);
        if (match && match[1]) {
          window.AimoImageViewer.openSingle(match[1], "World Backdrop");
        }
      });
    }

    document.querySelectorAll(".loc-backdrop-viewer-btn, .edit-loc-viewer-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const src = btn.getAttribute("data-viewer-src");
        const title = btn.getAttribute("data-viewer-title") || "";
        if (src) {
          window.AimoImageViewer.openSingle(src, title);
        }
      });
    });
  }
});
