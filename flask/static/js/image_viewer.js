(() => {
  let items = [];
  let currentIndex = 0;
  let lastFocusedEl = null;
  let touchStartX = null;
  let touchStartY = null;

  function getEls() {
    return {
      overlay: document.getElementById("aimo-image-viewer"),
      img: document.getElementById("aimo-iv-img"),
      title: document.getElementById("aimo-iv-title"),
      subtitle: document.getElementById("aimo-iv-subtitle"),
      counter: document.getElementById("aimo-iv-counter"),
      prevBtn: document.getElementById("aimo-iv-prev-btn"),
      nextBtn: document.getElementById("aimo-iv-next-btn"),
      closeBtn: document.getElementById("aimo-iv-close-btn"),
      stage: document.querySelector("#aimo-image-viewer .aimo-iv-stage"),
      imgWrap: document.querySelector("#aimo-image-viewer .aimo-iv-img-wrap"),
    };
  }

  function render() {
    const els = getEls();
    if (!els.overlay || !els.img || items.length === 0) return;

    const item = items[currentIndex];
    els.img.src = item.src;
    els.img.alt = item.alt || item.title || "";

    if (els.title) {
      els.title.textContent = item.title || "";
      els.title.style.display = item.title ? "" : "none";
    }
    if (els.subtitle) {
      els.subtitle.textContent = item.subtitle || "";
      els.subtitle.style.display = item.subtitle ? "" : "none";
    }

    const isGallery = items.length > 1;
    els.overlay.classList.toggle("is-gallery", isGallery);
    if (els.counter) {
      els.counter.textContent = isGallery ? `${currentIndex + 1} / ${items.length}` : "";
    }
    if (els.prevBtn) els.prevBtn.hidden = !isGallery;
    if (els.nextBtn) els.nextBtn.hidden = !isGallery;
  }

  function open(galleryItems, startIndex = 0) {
    const valid = (Array.isArray(galleryItems) ? galleryItems : [])
      .filter((item) => item && typeof item.src === "string" && item.src.trim() !== "");
    if (valid.length === 0) return;

    const { overlay } = getEls();
    if (!overlay) return;

    if (overlay.parentElement !== document.body) {
      document.body.appendChild(overlay);
    }

    items = valid;
    const idx = Number.isFinite(startIndex) ? Math.trunc(startIndex) : 0;
    currentIndex = Math.max(0, Math.min(items.length - 1, idx));
    lastFocusedEl = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    render();

    document.body.classList.add("aimo-iv-scroll-lock");
    overlay.classList.add("open");
    overlay.setAttribute("aria-hidden", "false");
    overlay.focus({ preventScroll: true });
  }

  function openSingle(src, title = "", subtitle = "") {
    if (!src) return;
    open([{ src, title, subtitle, alt: title }], 0);
  }

  function goTo(index) {
    if (items.length <= 1) return;
    currentIndex = ((index % items.length) + items.length) % items.length;
    render();
  }

  function next() {
    goTo(currentIndex + 1);
  }

  function prev() {
    goTo(currentIndex - 1);
  }

  function close() {
    const { overlay, img } = getEls();
    if (!overlay || !overlay.classList.contains("open")) return;

    overlay.classList.remove("open");
    overlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("aimo-iv-scroll-lock");
    if (img) img.removeAttribute("src");
    items = [];
    currentIndex = 0;

    if (lastFocusedEl && typeof lastFocusedEl.focus === "function") {
      lastFocusedEl.focus({ preventScroll: true });
    }
    lastFocusedEl = null;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const els = getEls();
    if (!els.overlay) return;

    if (els.overlay.parentElement !== document.body) {
      document.body.appendChild(els.overlay);
    }

    els.closeBtn?.addEventListener("click", (e) => {
      e.preventDefault();
      close();
    });

    els.prevBtn?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      prev();
    });

    els.nextBtn?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      next();
    });

    els.overlay.addEventListener("click", (e) => {
      if (e.target === els.overlay || e.target === els.stage || e.target === els.imgWrap) {
        close();
      }
    });

    els.overlay.addEventListener("touchstart", (e) => {
      if (e.touches.length !== 1) return;
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
    }, { passive: true });

    els.overlay.addEventListener("touchend", (e) => {
      if (touchStartX === null || touchStartY === null || items.length <= 1) {
        touchStartX = null;
        touchStartY = null;
        return;
      }
      const dx = e.changedTouches[0].clientX - touchStartX;
      const dy = e.changedTouches[0].clientY - touchStartY;
      touchStartX = null;
      touchStartY = null;

      if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.3) {
        if (dx < 0) next();
        else prev();
      }
    }, { passive: true });
  });

  document.addEventListener("keydown", (e) => {
    const { overlay } = getEls();
    if (!overlay || !overlay.classList.contains("open")) return;

    if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "ArrowLeft" && items.length > 1) {
      e.preventDefault();
      prev();
    } else if (e.key === "ArrowRight" && items.length > 1) {
      e.preventDefault();
      next();
    }
  });

  window.AimoImageViewer = {
    open,
    openSingle,
    next,
    prev,
    goTo,
    close,
  };
})();
