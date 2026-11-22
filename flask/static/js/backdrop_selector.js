document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-backdrop-selector]").forEach((root) => {
    const input = root.querySelector("[data-backdrop-input]");
    const preview = root.querySelector("[data-backdrop-preview]");
    const placeholder = root.querySelector("[data-backdrop-placeholder]");
    const removeBtn = root.querySelector("[data-backdrop-remove-btn]");
    const removeInput = root.querySelector("[data-backdrop-remove-input]");

    if (!preview) return;

    const notifyChange = (hasFile, removed) => {
      root.dispatchEvent(
        new CustomEvent("backdrop:change", {
          bubbles: true,
          detail: { hasFile, removed },
        })
      );
    };

    if (input) {
      input.addEventListener("change", () => {
        const file = input.files?.[0];
        if (!file) {
          notifyChange(false, false);
          return;
        }
        if (removeInput) removeInput.value = "0";
        const reader = new FileReader();
        reader.onload = (e) => {
          const result = e.target?.result;
          if (!result) return;
          preview.style.backgroundImage = `url('${result}')`;
          preview.setAttribute("data-backdrop-has-image", "1");
          preview.setAttribute("data-viewer-src", result);
          if (placeholder) placeholder.style.display = "none";
          if (removeBtn) removeBtn.style.display = "inline-flex";
          notifyChange(true, false);
        };
        reader.readAsDataURL(file);
      });
    }

    if (removeBtn) {
      removeBtn.addEventListener("click", () => {
        if (removeInput) removeInput.value = "1";
        if (input) input.value = "";
        preview.style.backgroundImage = "";
        preview.setAttribute("data-backdrop-has-image", "0");
        preview.removeAttribute("data-viewer-src");
        if (placeholder) placeholder.style.display = "";
        removeBtn.style.display = "none";
        notifyChange(false, true);
      });
    }

    preview.addEventListener("click", () => {
      if (preview.getAttribute("data-backdrop-has-image") !== "1") return;
      const src = preview.getAttribute("data-viewer-src");
      if (!src || !window.AimoImageViewer) return;
      const title = preview.getAttribute("data-viewer-title") || "";
      window.AimoImageViewer.openSingle(src, title);
    });
  });
});
