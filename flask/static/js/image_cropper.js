/**
 * AIMO Reusable Image Cropper Component
 * Provides responsive multi-target or single-target image cropping (1:1, 9:16, etc.)
 * with live previews, mouse & touch drag/resize, and DataTransfer file sync.
 */
window.AimoImageCropper = {
  setup(options) {
    const modalId = options.modalId;
    const modal = document.getElementById(modalId);
    if (!modal) return null;

    const fileInput = typeof options.fileInputId === "string"
      ? document.getElementById(options.fileInputId)
      : options.fileInputId;
    const openBtn = typeof options.openBtnId === "string"
      ? document.getElementById(options.openBtnId)
      : options.openBtnId;
    const statusBadge = typeof options.statusBadgeId === "string"
      ? document.getElementById(options.statusBadgeId)
      : options.statusBadgeId;

    const cropImg = document.getElementById(`${modalId}-source-img`);
    const cropBox = document.getElementById(`${modalId}-selection-box`);
    const resizeHandle = document.getElementById(`${modalId}-resize-handle`);
    const applyBtn = document.getElementById(`${modalId}-apply-btn`);

    if (!cropImg || !cropBox) return null;

    const targets = (options.targets || []).map((t) => ({
      id: t.id,
      ratio: t.ratio || 1.0,
      inputElement: t.inputElement,
      linkedInputElements: t.linkedInputElements || [],
      previewImgElement: t.previewImgElement,
      previewWrapElement: t.previewWrapElement,
      outputFilename: t.outputFilename || `${t.id}.png`,
      canvas: document.getElementById(`${modalId}-preview-canvas-${t.id}`),
    }));

    if (targets.length === 0) return null;

    let activeTargetId = targets[0].id;
    const boxes = {};
    targets.forEach((t) => {
      boxes[t.id] = { x: 0, y: 0, w: 0, h: 0, initialized: false };
    });

    let dragMode = null; // 'move' | 'resize' | null
    let startMouse = { x: 0, y: 0 };
    let startBox = { x: 0, y: 0, w: 0, h: 0 };
    let currentSourceDataUrl = "";
    let isInternalUpdate = false;

    function getTarget(id) {
      return targets.find((t) => t.id === id) || targets[0];
    }

    function initBoxForTarget(target) {
      const dispW = cropImg.clientWidth || 300;
      const dispH = cropImg.clientHeight || 300;
      if (dispW < 10 || dispH < 10) return;

      const r = target.ratio;
      let w, h;
      if (r < 1.0) {
        // e.g. Portrait 9:16
        h = dispH * 0.94;
        w = h * r;
        if (w > dispW * 0.94) {
          w = dispW * 0.94;
          h = w / r;
        }
      } else {
        // e.g. 1:1 Square or wide
        const maxSide = Math.min(dispW, dispH) * 0.88;
        w = maxSide;
        h = w / r;
        if (h > dispH * 0.94) {
          h = dispH * 0.94;
          w = h * r;
        }
      }

      boxes[target.id] = {
        w: Math.max(32, Math.round(w)),
        h: Math.max(32, Math.round(h)),
        x: Math.max(0, Math.round((dispW - w) / 2)),
        y: Math.max(0, Math.round((dispH - h) / 2)),
        initialized: true,
      };
    }

    function clampActiveBox() {
      const dispW = cropImg.clientWidth || 300;
      const dispH = cropImg.clientHeight || 300;
      if (dispW < 10 || dispH < 10) return;

      const current = getTarget(activeTargetId);
      const box = boxes[activeTargetId];
      const ratio = current.ratio;

      box.w = Math.max(32, Math.min(dispW, box.w));
      box.h = Math.round(box.w / ratio);
      if (box.h > dispH) {
        box.h = dispH;
        box.w = Math.round(box.h * ratio);
      }
      box.x = Math.max(0, Math.min(dispW - box.w, box.x));
      box.y = Math.max(0, Math.min(dispH - box.h, box.y));
    }

    function renderActiveBox() {
      clampActiveBox();
      const box = boxes[activeTargetId];
      cropBox.style.left = `${box.x}px`;
      cropBox.style.top = `${box.y}px`;
      cropBox.style.width = `${box.w}px`;
      cropBox.style.height = `${box.h}px`;
      cropBox.setAttribute("data-target", activeTargetId);
      updateAllMiniPreviews();
    }

    function getNaturalCropRect(box) {
      const dispW = cropImg.clientWidth || 1;
      const dispH = cropImg.clientHeight || 1;
      const natW = cropImg.naturalWidth || dispW;
      const natH = cropImg.naturalHeight || dispH;
      const scaleX = natW / dispW;
      const scaleY = natH / dispH;
      return {
        sx: Math.max(0, Math.round(box.x * scaleX)),
        sy: Math.max(0, Math.round(box.y * scaleY)),
        sw: Math.max(1, Math.min(natW, Math.round(box.w * scaleX))),
        sh: Math.max(1, Math.min(natH, Math.round(box.h * scaleY))),
      };
    }

    function updateAllMiniPreviews() {
      if (!cropImg.complete || !cropImg.naturalWidth) return;
      targets.forEach((t) => {
        if (!t.canvas) return;
        const rect = getNaturalCropRect(boxes[t.id]);
        const ctx = t.canvas.getContext("2d");
        ctx.clearRect(0, 0, t.canvas.width, t.canvas.height);
        ctx.drawImage(
          cropImg,
          rect.sx,
          rect.sy,
          rect.sw,
          rect.sh,
          0,
          0,
          t.canvas.width,
          t.canvas.height
        );
      });
    }

    function setActiveTarget(targetId) {
      activeTargetId = targetId;
      modal.querySelectorAll("[data-crop-target]").forEach((el) => {
        el.classList.toggle("active", el.getAttribute("data-crop-target") === targetId);
      });
      if (!boxes[targetId].initialized) {
        initBoxForTarget(getTarget(targetId));
      }
      renderActiveBox();
    }

    function openModalWithSrc(src) {
      if (!src) return;

      if (window.AimoModals && typeof window.AimoModals.open === "function") {
        window.AimoModals.open(modalId);
      } else {
        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");
      }

      const onImageReady = () => {
        setTimeout(() => {
          targets.forEach((t) => initBoxForTarget(t));
          setActiveTarget(activeTargetId);
        }, 80);
      };

      if (cropImg.src === src && cropImg.complete && cropImg.naturalWidth) {
        onImageReady();
      } else {
        cropImg.onload = onImageReady;
        cropImg.src = src;
      }
    }

    // Modal switch triggers
    modal.querySelectorAll("[data-crop-target]").forEach((el) => {
      el.addEventListener("click", () => {
        const tid = el.getAttribute("data-crop-target");
        if (tid) setActiveTarget(tid);
      });
    });

    // File input change trigger
    if (fileInput) {
      fileInput.addEventListener("change", () => {
        if (isInternalUpdate) return;
        const file = fileInput.files && fileInput.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (ev) => {
          currentSourceDataUrl = ev.target.result;
          if (openBtn) openBtn.disabled = false;
          openModalWithSrc(currentSourceDataUrl);
        };
        reader.readAsDataURL(file);
      });
    }

    // Explicit open button trigger
    if (openBtn) {
      openBtn.addEventListener("click", () => {
        const fallbackTarget = targets[0];
        const src =
          currentSourceDataUrl ||
          (fallbackTarget.previewImgElement ? fallbackTarget.previewImgElement.getAttribute("src") : "") ||
          cropImg.getAttribute("src");
        if (src) openModalWithSrc(src);
      });
    }

    // Drag & Resize Handlers
    function startDrag(clientX, clientY, targetEl) {
      dragMode = targetEl === resizeHandle ? "resize" : "move";
      startMouse = { x: clientX, y: clientY };
      startBox = { ...boxes[activeTargetId] };
      document.body.style.userSelect = "none";
    }

    function moveDrag(clientX, clientY) {
      if (!dragMode) return;
      const dx = clientX - startMouse.x;
      const dy = clientY - startMouse.y;
      const box = boxes[activeTargetId];
      const target = getTarget(activeTargetId);

      if (dragMode === "move") {
        box.x = startBox.x + dx;
        box.y = startBox.y + dy;
      } else if (dragMode === "resize") {
        box.w = Math.max(32, startBox.w + dx);
        box.h = Math.round(box.w / target.ratio);
      }
      renderActiveBox();
    }

    function endDrag() {
      dragMode = null;
      document.body.style.userSelect = "";
    }

    cropBox.addEventListener("mousedown", (e) => {
      e.preventDefault();
      startDrag(e.clientX, e.clientY, e.target);
    });

    window.addEventListener("mousemove", (e) => {
      moveDrag(e.clientX, e.clientY);
    });

    window.addEventListener("mouseup", endDrag);

    cropBox.addEventListener("touchstart", (e) => {
      if (e.touches && e.touches.length === 1) {
        e.preventDefault();
        startDrag(e.touches[0].clientX, e.touches[0].clientY, e.target);
      }
    }, { passive: false });

    window.addEventListener("touchmove", (e) => {
      if (dragMode && e.touches && e.touches.length === 1) {
        e.preventDefault();
        moveDrag(e.touches[0].clientX, e.touches[0].clientY);
      }
    }, { passive: false });

    window.addEventListener("touchend", endDrag);
    window.addEventListener("touchcancel", endDrag);

    // Apply crops
    applyBtn?.addEventListener("click", async () => {
      if (!cropImg.complete || !cropImg.naturalWidth) return;

      const results = [];
      for (const t of targets) {
        const rect = getNaturalCropRect(boxes[t.id]);
        const offCanvas = document.createElement("canvas");
        offCanvas.width = rect.sw;
        offCanvas.height = rect.sh;
        const ctx = offCanvas.getContext("2d");
        ctx.drawImage(cropImg, rect.sx, rect.sy, rect.sw, rect.sh, 0, 0, rect.sw, rect.sh);

        const blob = await new Promise((resolve) => offCanvas.toBlob(resolve, "image/png"));
        if (!blob) continue;

        const file = new File([blob], t.outputFilename, { type: "image/png" });
        results.push({ target: t, blob, file });
      }

      isInternalUpdate = true;
      try {
        results.forEach(({ target: t, file, blob }) => {
          if (t.inputElement) {
            try {
              const dt = new DataTransfer();
              dt.items.add(file);
              t.inputElement.files = dt.files;
            } catch (err) {
              console.warn("DataTransfer update failed:", err);
            }
          }
          (t.linkedInputElements || []).forEach((linkedEl) => {
            if (linkedEl) {
              try {
                const dt = new DataTransfer();
                dt.items.add(new File([blob], file.name, { type: file.type }));
                linkedEl.files = dt.files;
              } catch (_) {}
            }
          });

          const blobUrl = URL.createObjectURL(blob);
          if (t.previewImgElement) t.previewImgElement.src = blobUrl;
          if (t.previewWrapElement) t.previewWrapElement.style.display = "block";
        });
      } finally {
        isInternalUpdate = false;
      }

      if (statusBadge) {
        const activeLabel = targets.length > 1
          ? (window.t ? window.t("Crops active") : "Crops active")
          : (window.t ? window.t("1:1 Cover active") : "1:1 Cover active");
        statusBadge.textContent = "✓ " + activeLabel;
        statusBadge.style.display = "inline-block";
      }

      if (typeof options.onApplied === "function") {
        options.onApplied(results);
      }

      if (window.AimoModals && typeof window.AimoModals.close === "function") {
        window.AimoModals.close(modalId);
      } else {
        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");
      }
    });

    return {
      openWithSrc: openModalWithSrc,
      setActiveTarget,
    };
  },
};
