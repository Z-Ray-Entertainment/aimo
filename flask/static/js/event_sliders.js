// Reusable Dual-Thumb Relationship Range Sliders (.aimo-dual-range)
if (!window.AIMO_EVENT_SLIDERS_LOADED) {
  window.AIMO_EVENT_SLIDERS_LOADED = true;
  // Reusable Dual-Thumb Relationship Range Sliders (.aimo-dual-range)
  const initDualRangeSliders = () => {
    document.querySelectorAll(".aimo-dual-range").forEach((root) => {
      if (root.dataset.initialized === "1") return;
      root.dataset.initialized = "1";

      const minInput = root.querySelector(".aimo-dual-range-min");
      const maxInput = root.querySelector(".aimo-dual-range-max");
      const fillEl = root.querySelector(".aimo-dual-range-fill");
      const labelEl = root.querySelector(".aimo-dual-range-label");
      const wrapEl = root.querySelector(".aimo-dual-range-wrap");
      if (!minInput || !maxInput) return;

      let tiersMap = {};
      try {
        tiersMap = JSON.parse(root.getAttribute("data-tiers") || "{}");
      } catch (_) {
        tiersMap = {};
      }

      const updateZOrder = (cursorPct = null) => {
        const minVal = parseInt(minInput.value, 10);
        const maxVal = parseInt(maxInput.value, 10);
        if (minVal === maxVal) {
          if (maxVal >= 100) {
            minInput.style.zIndex = "4";
            maxInput.style.zIndex = "3";
          } else if (minVal <= -100) {
            minInput.style.zIndex = "3";
            maxInput.style.zIndex = "4";
          } else if (cursorPct !== null && cursorPct < ((minVal + 100) / 200) * 100) {
            minInput.style.zIndex = "4";
            maxInput.style.zIndex = "3";
          } else {
            minInput.style.zIndex = "3";
            maxInput.style.zIndex = "4";
          }
        } else {
          minInput.style.zIndex = "3";
          maxInput.style.zIndex = "4";
        }
      };

      const render = (source) => {
        let minVal = parseInt(minInput.value, 10);
        let maxVal = parseInt(maxInput.value, 10);
        if (source === "min" && minVal > maxVal) {
          minVal = maxVal;
          minInput.value = String(minVal);
        } else if (source === "max" && maxVal < minVal) {
          maxVal = minVal;
          maxInput.value = String(maxVal);
        }

        const minPct = Math.max(0, Math.min(100, ((minVal + 100) / 200) * 100));
        const maxPct = Math.max(0, Math.min(100, ((maxVal + 100) / 200) * 100));
        if (fillEl) {
          fillEl.style.clipPath = `inset(0 ${100 - maxPct}% 0 ${minPct}%)`;
        }
        if (labelEl) {
          const minName = tiersMap[String(minVal)] ?? String(minVal);
          const maxName = tiersMap[String(maxVal)] ?? String(maxVal);
          labelEl.textContent = `${minName} – ${maxName}`;
        }
        updateZOrder();
      };

      minInput.addEventListener("input", () => render("min"));
      maxInput.addEventListener("input", () => render("max"));
      if (wrapEl) {
        const handlePointer = (e) => {
          const rect = wrapEl.getBoundingClientRect();
          if (rect.width > 0) {
            const pct = ((e.clientX - rect.left) / rect.width) * 100;
            updateZOrder(pct);
          }
        };
        wrapEl.addEventListener("pointermove", handlePointer);
        wrapEl.addEventListener("pointerdown", handlePointer);
      }

      render(null);
    });
  };

  initDualRangeSliders();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDualRangeSliders);
  } else {
    initDualRangeSliders();
  }
}
