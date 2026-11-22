import { escapeHtml } from "./markdown.js";
import { appendUiNotice as renderUiNotice } from "./message_renderer.js";

export function appendImageToGallery(imgUrl, mediaKey) {
  const grid = document.getElementById("session-media-grid");
  if (!grid || !imgUrl) return null;
  const emptyMsg = document.getElementById("session-media-empty");
  if (emptyMsg) emptyMsg.remove();

  if (mediaKey) {
    const existing = grid.querySelector(`[data-media-path="${CSS.escape(mediaKey)}"]`);
    if (existing) {
      const img = existing.querySelector("img");
      if (img) img.src = imgUrl;
      return existing;
    }
  }

  const tile = document.createElement("div");
  tile.className = "aimo-card-tile";
  tile.style.backgroundImage = `url('${encodeURI(imgUrl)}')`;
  if (mediaKey) {
    tile.setAttribute("data-media-path", mediaKey);
  }
  tile.innerHTML = `<img src="${escapeHtml(imgUrl)}" alt="Chat Media" style="display: none;">`;
  grid.appendChild(tile);
  return tile;
}

export function showLocationSwitchCountdown(stream, locationObj) {
  const bannerContainer = document.getElementById("location-switch-container");
  if (!bannerContainer) return;

  if (stream.countdownTimer) {
    clearInterval(stream.countdownTimer);
  }

  bannerContainer.innerHTML = `
    <div class="location-prompt-banner" id="loc-prompt-banner">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:1rem;">
        <span>Zu <strong>${escapeHtml(locationObj.name)}</strong> wechseln?</span>
        <div style="display:flex; gap:0.5rem;">
          <button type="button" class="btn" id="loc-confirm-yes">Ja</button>
          <button type="button" class="btn btn-danger" id="loc-confirm-no">Nein</button>
        </div>
      </div>
      <div class="countdown-bar-track">
        <div class="countdown-bar-fill" id="loc-countdown-fill"></div>
      </div>
    </div>
  `;

  let remaining = 60;
  let isPaused = false;
  const fillEl = document.getElementById("loc-countdown-fill");
  const bannerEl = document.getElementById("loc-prompt-banner");

  if (bannerEl) {
    bannerEl.addEventListener("mouseenter", () => {
      isPaused = true;
    });
    bannerEl.addEventListener("mouseleave", () => {
      isPaused = false;
    });
  }

  stream.countdownTimer = setInterval(() => {
    if (isPaused) return;
    remaining -= 1;
    if (fillEl) {
      fillEl.style.width = `${(remaining / 60) * 100}%`;
    }
    if (remaining <= 0) {
      clearInterval(stream.countdownTimer);
      bannerContainer.innerHTML = "";
    }
  }, 1000);

  document.getElementById("loc-confirm-no")?.addEventListener("click", () => {
    clearInterval(stream.countdownTimer);
    bannerContainer.innerHTML = "";
  });

  document.getElementById("loc-confirm-yes")?.addEventListener("click", async () => {
    clearInterval(stream.countdownTimer);
    bannerContainer.innerHTML = "";
    await stream.switchLocation(locationObj.id);
  });
}

export function decrementEventCounterOptimistic() {
  const statusEl = document.getElementById("admin-event-counter-status");
  const valEl = document.getElementById("admin-event-counter-val");
  if (!statusEl) return;
  const eventsToggle = document.getElementById("toggle-events-checkbox");
  if (eventsToggle && !eventsToggle.checked) return;
  if (statusEl.textContent.includes("(pausiert)")) return;

  let currentVal = valEl ? parseInt(valEl.textContent.trim(), 10) : NaN;
  if (isNaN(currentVal)) {
    if (statusEl.textContent.includes("nächste Nachricht")) {
      currentVal = 1;
    } else {
      return;
    }
  }

  const nextVal = Math.max(0, currentVal - 1);
  if (nextVal <= 1) {
    statusEl.innerHTML = `<strong id="admin-event-counter-val">nächste Nachricht</strong>`;
  } else {
    statusEl.innerHTML = `in <strong id="admin-event-counter-val">${nextVal}</strong> Nachrichten`;
  }
}

export function updateEventCounter(counter, eventsEnabled) {
  const statusEl = document.getElementById("admin-event-counter-status");
  if (!statusEl || counter === undefined || counter === null) return;
  const isPaused = eventsEnabled === false;
  const val = parseInt(counter, 10);
  if (isNaN(val)) return;

  if (isPaused) {
    statusEl.innerHTML = `in <strong id="admin-event-counter-val">${val}</strong> ${val === 1 ? "Nachricht" : "Nachrichten"} <span class="counter-paused-label">(pausiert)</span>`;
  } else if (val <= 1) {
    statusEl.innerHTML = `<strong id="admin-event-counter-val">nächste Nachricht</strong>`;
  } else {
    statusEl.innerHTML = `in <strong id="admin-event-counter-val">${val}</strong> Nachrichten`;
  }
}

export async function switchLocation(stream, locationId) {
  if (locationId === undefined) return null;
  const resp = await fetch(`/api/chat/${stream.sessionId}/switch-location`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ location_id: locationId }),
  });
  const resData = await resp.json().catch(() => ({}));
  if (resp.ok) {
    if (resData.system_message) {
      stream.appendSystemMessage(resData.system_message);
    } else if (resData.ui_notice) {
      renderUiNotice(resData.ui_notice);
    }
    const backdrop = document.getElementById("system-default-backdrop") || document.querySelector(".system-default-backdrop");
    if (backdrop) {
      const locBgPath = resData.location?.background_image_path;
      const worldBgPath = resData.worldinfo_backdrop_path;
      const effectivePath = (locBgPath && locBgPath.trim())
        ? locBgPath.trim()
        : ((worldBgPath && worldBgPath.trim()) ? worldBgPath.trim() : "");
      if (effectivePath) {
        const bgUrl = (effectivePath.startsWith("/") || effectivePath.startsWith("http"))
          ? effectivePath
          : `/uploads/${effectivePath}`;
        backdrop.style.backgroundImage = `url('${bgUrl}')`;
        document.body.style.setProperty("--system-backdrop-url", `url('${bgUrl}')`);
      } else {
        const worldBackdropAttr = backdrop.getAttribute("data-world-backdrop");
        const defaultBackdrop = (worldBackdropAttr && worldBackdropAttr.trim())
          ? worldBackdropAttr.trim()
          : (backdrop.getAttribute("data-default-backdrop") || "/static/img/cover.svg");
        backdrop.style.backgroundImage = `url('${defaultBackdrop}')`;
        document.body.style.setProperty("--system-backdrop-url", `url('${defaultBackdrop}')`);
      }
    }
    const locIndicator = document.getElementById("chat-location-indicator");
    if (locIndicator) {
      if (resData.location?.name) {
        locIndicator.innerHTML = `📍 ${escapeHtml(window.t ? window.t("Location:") : "Location:")} <strong>${escapeHtml(resData.location.name)}</strong>`;
      } else if (resData.worldinfo?.name) {
        locIndicator.innerHTML = `🌐 ${escapeHtml(window.t ? window.t("World:") : "World:")} <strong>${escapeHtml(resData.worldinfo.name)}</strong>`;
      }
    }
    const locSelect = document.getElementById("chat-location-select");
    if (locSelect) {
      locSelect.value = locationId === null ? "world" : String(locationId);
    }
    const locBackdropBtn = document.getElementById("chat-location-backdrop-btn");
    if (locBackdropBtn) {
      const locBgPath = resData.location?.background_image_path?.trim();
      if (locBgPath) {
        const bgUrl = (locBgPath.startsWith("/") || locBgPath.startsWith("http"))
          ? locBgPath
          : `/uploads/${locBgPath}`;
        locBackdropBtn.setAttribute("data-backdrop-url", bgUrl);
        locBackdropBtn.setAttribute("data-backdrop-title", resData.location?.name || "");
        locBackdropBtn.hidden = false;
      } else {
        locBackdropBtn.setAttribute("data-backdrop-url", "");
        locBackdropBtn.setAttribute("data-backdrop-title", "");
        locBackdropBtn.hidden = true;
      }
    }
    return resData;
  } else {
    const errStr = resData.error || "Fehler beim Wechseln des Ortes.";
    window.showToastError ? window.showToastError(errStr) : alert(errStr);
  }
  return null;
}

export async function triggerComfyUIGeneration(stream) {
  if (stream.isGeneratingImage) return;
  stream.isGeneratingImage = true;

  const input = document.querySelector("#chat-input-form textarea, #chat-input-form input[name='message']");
  const submitBtn = document.getElementById("chat-send-btn") || document.querySelector("#chat-input-form button[type='submit']");
  const regenBtn = document.getElementById("chat-regenerate-btn");
  const cancelBtn = document.getElementById("cancel-image-gen-btn");
  const messagesList = document.getElementById("chat-messages-list");

  if (input) input.disabled = true;
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.style.display = "none";
  }
  if (regenBtn) {
    regenBtn.disabled = true;
    regenBtn.style.display = "none";
  }
  if (cancelBtn) cancelBtn.style.display = "inline-flex";

  const notice = document.createElement("div");
  notice.className = "system-ui-notice";
  notice.textContent = window.t ? window.t("Generating image...") : "Generating image...";
  if (messagesList) {
    messagesList.appendChild(notice);
    messagesList.scrollTop = messagesList.scrollHeight;
  }

  try {
    const resp = await fetch(`/api/chat/${stream.sessionId}/generate-image`, {
      method: "POST",
    });
    const data = await resp.json();
    if (resp.ok && data.image_path) {
      notice.innerHTML = `<img src="/uploads/${data.image_path}" alt="Generierte Szene" class="chat-generated-scene-img" style="max-width:320px; border-radius:10px; border:2px solid var(--gold-accent); margin-top:0.4rem;">`;
      appendImageToGallery(`/uploads/${data.image_path}`, data.image_path);
    } else {
      notice.textContent = data.error || "Bildgenerierung abgebrochen oder fehlgeschlagen.";
    }
  } finally {
    stream.isGeneratingImage = false;
    if (input) input.disabled = false;
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.style.display = "";
    }
    if (regenBtn) {
      regenBtn.disabled = false;
      regenBtn.style.display = "inline-flex";
    }
    if (cancelBtn) cancelBtn.style.display = "none";
  }
}

export async function cancelComfyUIGeneration(stream) {
  await fetch(`/api/chat/${stream.sessionId}/cancel-image`, { method: "POST" });
  stream.isGeneratingImage = false;
  const input = document.querySelector("#chat-input-form textarea, #chat-input-form input[name='message']");
  const submitBtn = document.getElementById("chat-send-btn") || document.querySelector("#chat-input-form button[type='submit']");
  const regenBtn = document.getElementById("chat-regenerate-btn");
  const cancelBtn = document.getElementById("cancel-image-gen-btn");
  if (input) input.disabled = false;
  if (submitBtn) {
    submitBtn.disabled = false;
    submitBtn.style.display = "";
  }
  if (regenBtn) {
    regenBtn.disabled = false;
    regenBtn.style.display = "inline-flex";
  }
  if (cancelBtn) cancelBtn.style.display = "none";
}

export function openGridGallery(gridEl, clickedTile) {
  if (!window.AimoImageViewer || !gridEl || !clickedTile) return;
  const tiles = Array.from(gridEl.querySelectorAll(".aimo-card-tile"));
  const items = [];
  let startIndex = 0;

  for (const tile of tiles) {
    const img = tile.querySelector("img");
    const src = img?.getAttribute("src") || img?.src;
    if (!src) continue;
    if (tile === clickedTile) {
      startIndex = items.length;
    }
    items.push({
      src,
      title: tile.getAttribute("data-viewer-title") || img.getAttribute("alt") || "",
      subtitle: tile.getAttribute("data-viewer-subtitle") || "",
      alt: img.getAttribute("alt") || "",
    });
  }

  if (items.length > 0) {
    window.AimoImageViewer.open(items, startIndex);
  }
}

export function initImageViewerBindings(stream) {
  const openSingle = (src, title = "", subtitle = "") => {
    if (window.AimoImageViewer && src) {
      window.AimoImageViewer.openSingle(src, title, subtitle);
    }
  };

  const sidebarSprite = document.getElementById("active-character-sprite");
  if (sidebarSprite) {
    sidebarSprite.addEventListener("click", (e) => {
      e.stopPropagation();
      const meta = stream.getChatMetadata();
      openSingle(sidebarSprite.src, meta.characterName || sidebarSprite.alt || "");
    });
  }

  const bindBackdropBtn = (btnId) => {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.addEventListener("click", () => {
      const url = btn.getAttribute("data-backdrop-url");
      const title = btn.getAttribute("data-backdrop-title") || "";
      if (url) openSingle(url, title);
    });
  };
  bindBackdropBtn("chat-world-backdrop-btn");
  bindBackdropBtn("chat-location-backdrop-btn");

  const messagesList = document.getElementById("chat-messages-list");
  if (messagesList) {
    messagesList.addEventListener("click", (e) => {
      const target = e.target;
      if (!(target instanceof Element)) return;

      const charAvatar = target.closest(".chat-bubble-row.character .chat-avatar");
      if (charAvatar) {
        const meta = stream.getChatMetadata();
        openSingle(charAvatar.src, meta.characterName || charAvatar.alt || "");
        return;
      }

      const uploadedImg = target.closest(".chat-uploaded-image-wrap img");
      if (uploadedImg) {
        openSingle(uploadedImg.src, uploadedImg.getAttribute("alt") || "");
        return;
      }

      const generatedImg = target.closest(".chat-generated-scene-img");
      if (generatedImg) {
        openSingle(generatedImg.src, generatedImg.getAttribute("alt") || "");
      }
    });
  }

  const unlockedGrid = document.getElementById("unlocked-gallery-grid");
  if (unlockedGrid) {
    unlockedGrid.addEventListener("click", (e) => {
      const tile = e.target instanceof Element ? e.target.closest(".aimo-card-tile") : null;
      if (tile) openGridGallery(unlockedGrid, tile);
    });
  }

  const sessionMediaGrid = document.getElementById("session-media-grid");
  if (sessionMediaGrid) {
    sessionMediaGrid.addEventListener("click", (e) => {
      const tile = e.target instanceof Element ? e.target.closest(".aimo-card-tile") : null;
      if (tile) openGridGallery(sessionMediaGrid, tile);
    });
  }
}
