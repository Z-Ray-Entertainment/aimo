window.showToast = function showToast(options) {
  const container = document.getElementById("aimo-toast-container");
  if (!container || !options) return null;

  const config = typeof options === "string" ? { message: options } : options;
  let type = String(config.type || "info").toLowerCase();
  if (type === "danger") type = "error";

  const defaultTitles = {
    success: window.t ? window.t("Success") : "Success",
    warning: window.t ? window.t("Warning") : "Warning",
    error: window.t ? window.t("Error") : "Error",
    info: window.t ? window.t("Notice") : "Notice",
  };

  const defaultIcons = {
    success: "✓",
    warning: "⚠️",
    error: "✕",
    info: "ℹ️",
  };

  const toast = document.createElement("div");
  toast.className = `aimo-toast toast-${type} aimo-frame`;
  toast.setAttribute("role", type === "error" ? "alert" : "status");

  let mediaHtml = "";
  if (config.image) {
    mediaHtml = `<img src="${config.image}" alt="" class="aimo-toast-image" onerror="this.src='/static/img/cover.svg'">`;
  } else {
    const iconText = config.icon !== undefined ? config.icon : (defaultIcons[type] || "ℹ️");
    if (iconText) {
      mediaHtml = `<div class="aimo-toast-icon" aria-hidden="true">${iconText}</div>`;
    }
  }

  const titleText = config.title !== undefined ? config.title : (defaultTitles[type] || "");
  const messageText = config.message || "";

  const buttonConfigs = [];
  if (config.button) buttonConfigs.push(config.button);
  if (Array.isArray(config.buttons)) buttonConfigs.push(...config.buttons);

  const actionsHtml = buttonConfigs.length > 0 ? `<div class="aimo-toast-actions"></div>` : "";

  toast.innerHTML = `
    ${mediaHtml}
    <div class="aimo-toast-body">
      ${titleText ? `<div class="aimo-toast-title"></div>` : ""}
      <div class="aimo-toast-message"></div>
      ${actionsHtml}
    </div>
    <button type="button" class="aimo-toast-close" title="${window.t ? window.t("Close") : "Close"}" aria-label="${window.t ? window.t("Close") : "Close"}">✕</button>
  `;

  if (titleText) {
    const titleEl = toast.querySelector(".aimo-toast-title");
    if (titleEl) titleEl.textContent = titleText;
  }

  const msgEl = toast.querySelector(".aimo-toast-message");
  if (msgEl) msgEl.textContent = messageText;

  let isClosing = false;
  const removeToast = () => {
    if (isClosing) return;
    isClosing = true;
    toast.classList.add("closing");
    setTimeout(() => {
      try {
        toast.remove();
      } catch (_) {}
    }, 240);
  };

  if (buttonConfigs.length > 0) {
    const actionsContainer = toast.querySelector(".aimo-toast-actions");
    buttonConfigs.forEach((btnCfg) => {
      if (!btnCfg || !btnCfg.text) return;
      const btnEl = document.createElement(btnCfg.href ? "a" : "button");
      btnEl.className = `aimo-btn btn aimo-toast-btn ${btnCfg.className || ""}`;
      btnEl.textContent = btnCfg.text;
      if (btnCfg.href) {
        btnEl.setAttribute("href", btnCfg.href);
      } else {
        btnEl.setAttribute("type", "button");
      }
      btnEl.addEventListener("click", (evt) => {
        if (typeof btnCfg.onClick === "function") {
          btnCfg.onClick(toast, evt);
        }
        if (btnCfg.autoClose !== false && !btnCfg.href) {
          removeToast();
        }
      });
      actionsContainer.appendChild(btnEl);
    });
  }

  toast.querySelector(".aimo-toast-close")?.addEventListener("click", removeToast);
  container.appendChild(toast);

  const duration = config.duration !== undefined
    ? config.duration
    : (type === "error" ? 9000 : type === "warning" ? 7000 : 5000);

  if (duration > 0) {
    setTimeout(removeToast, duration);
  }

  return toast;
};

window.showToastSuccess = function showToastSuccess(message, title = "Erfolg", duration = 5000) {
  return window.showToast({ type: "success", title, message, duration });
};

window.showToastWarning = function showToastWarning(message, title = "Warnung", duration = 7000) {
  return window.showToast({ type: "warning", title, message, duration });
};

window.showToastError = function showToastError(message, title = "Fehler", duration = 9000) {
  return window.showToast({ type: "error", title, message, duration });
};

window.showToastInfo = function showToastInfo(message, title = "Hinweis", duration = 6000) {
  return window.showToast({ type: "info", title, message, duration });
};

window.showAimoToast = function showAimoToast(notif) {
  if (!notif) return;
  const portraitUrl = notif.character_portrait ? `/uploads/${notif.character_portrait}` : "/static/img/cover.svg";
  const rawPreview = String(notif.localized_content || "").replace(/\s+/g, " ").trim();
  const preview = rawPreview.length > 110 ? `${rawPreview.slice(0, 110)}…` : rawPreview;

  return window.showToast({
    type: "info",
    title: `💬 ${notif.character_name || "Charakter"} hat geantwortet`,
    message: preview,
    image: portraitUrl,
    button: {
      text: "Zum Chat →",
      href: `/chat/session/${notif.session_id}`,
    },
    duration: 9000,
  });
};

function triggerFlashedMessages() {
  const flashedDataEl = document.getElementById("aimo-flashed-data");
  if (!flashedDataEl) return;
  try {
    const flashedMessages = JSON.parse(flashedDataEl.textContent || "[]");
    if (Array.isArray(flashedMessages)) {
      flashedMessages.forEach(([category, message]) => {
        window.showToast({
          type: category || "info",
          message: message,
        });
      });
    }
  } catch (e) {
    console.error("Failed to parse flashed messages:", e);
  }
}

function triggerPendingTranslationToast() {
  const marker = document.getElementById("overview-missing-translations");
  if (!marker || typeof window.showToastInfo !== "function") return;
  const msg = marker.getAttribute("data-message") || "";
  const title = marker.getAttribute("data-title") || "Info";
  if (msg) {
    window.showToastInfo(msg, title, 8000);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", triggerFlashedMessages);
  document.addEventListener("DOMContentLoaded", triggerPendingTranslationToast);
} else {
  triggerFlashedMessages();
  triggerPendingTranslationToast();
}
