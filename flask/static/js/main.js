window.toggleSecretVisibility = function toggleSecretVisibility(inputId, btnEl) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPassword = input.type === "password";
  input.type = isPassword ? "text" : "password";
  if (btnEl) {
    btnEl.title = isPassword ? "API-Key verbergen" : "API-Key anzeigen";
  }
};


window.aimoThinkingDotsHtml = function aimoThinkingDotsHtml() {
  return '<span class="thinking-dots" aria-hidden="true"><span></span><span></span><span></span></span>';
};

/**
 * Puts an action button into the standardized loading state with animated thinking dots.
 * @param {HTMLElement|string} btn - Button element or selector
 * @param {string} label - Active loading text (e.g. "Analysiere Bild", "Entwerfe Dialog")
 * @returns {string} Original button innerHTML for later restoration
 */
window.setButtonLoading = function setButtonLoading(btn, label) {
  const el = typeof btn === "string" ? document.querySelector(btn) : btn;
  if (!el) return "";
  const origHtml = el.innerHTML;
  el.classList.add("is-loading");
  el.disabled = true;
  el.innerHTML = `${window.aimoThinkingDotsHtml()} <span>${label || ""}</span>`;
  return origHtml;
};

/**
 * Restores an action button from the loading state.
 * @param {HTMLElement|string} btn - Button element or selector
 * @param {string} [restoreHtml] - Optional HTML to restore. If omitted, retains current text but removes is-loading and re-enables.
 */
window.resetButtonLoading = function resetButtonLoading(btn, restoreHtml) {
  const el = typeof btn === "string" ? document.querySelector(btn) : btn;
  if (!el) return;
  el.classList.remove("is-loading");
  el.disabled = false;
  if (restoreHtml !== undefined && restoreHtml !== null) {
    el.innerHTML = restoreHtml;
  }
};

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

  // Media element: image takes precedence over icon
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

  // Support single 'button' or array of 'buttons'
  const buttonConfigs = [];
  if (config.button) buttonConfigs.push(config.button);
  if (Array.isArray(config.buttons)) buttonConfigs.push(...config.buttons);

  let actionsHtml = "";
  if (buttonConfigs.length > 0) {
    actionsHtml = `<div class="aimo-toast-actions"></div>`;
  }

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

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", triggerFlashedMessages);
} else {
  triggerFlashedMessages();
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
  document.addEventListener("DOMContentLoaded", triggerPendingTranslationToast);
} else {
  triggerPendingTranslationToast();
}

document.addEventListener("DOMContentLoaded", () => {
  try {
    const sysLang = (navigator.language || "de").slice(0, 2).toLowerCase();
    document.cookie = `aimo_sys_lang=${encodeURIComponent(sysLang)}; path=/; max-age=31536000; SameSite=Lax`;
  } catch (_) {}

  // Generic Tab Switcher
  document.querySelectorAll("[data-tab-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab-target");
      const group = btn.closest("[data-tab-group]") || document;
      group.querySelectorAll("[data-tab-target]").forEach((b) => b.classList.remove("active"));
      group.querySelectorAll(".tab-pane").forEach((pane) => pane.classList.remove("active"));
      btn.classList.add("active");
      const pane = document.getElementById(targetId);
      if (pane) {
        pane.classList.add("active");
      }
      if (targetId.startsWith("tab-")) {
        const tabKey = targetId.replace(/^tab-char-/, "").replace(/^tab-/, "");
        const url = new URL(window.location.href);
        url.searchParams.set("tab", tabKey);
        window.history.replaceState({}, "", url.toString());
        document.querySelectorAll('input[name="active_tab"]').forEach((inp) => {
          inp.value = tabKey;
        });
        document.querySelectorAll("form").forEach((f) => {
          if (f.action) {
            try {
              const fUrl = new URL(f.action, window.location.origin);
              if (fUrl.pathname === window.location.pathname) {
                fUrl.searchParams.set("tab", tabKey);
                f.action = fUrl.toString();
              }
            } catch (_) {}
          }
        });
      }
    });
  });


  // Mobile Hamburger Menu Toggle & Interactions
  const mobileToggle = document.getElementById("mobile-menu-toggle");
  const mobileMenu = document.getElementById("mobile-dropdown-menu");

  const closeMobileMenu = () => {
    if (mobileMenu && mobileMenu.classList.contains("open")) {
      mobileMenu.classList.remove("open");
      mobileMenu.setAttribute("aria-hidden", "true");
      if (mobileToggle) {
        mobileToggle.classList.remove("open");
        mobileToggle.setAttribute("aria-expanded", "false");
        mobileToggle.setAttribute("aria-label", "Menü öffnen");
      }
    }
  };

  const toggleMobileMenu = () => {
    if (!mobileMenu || !mobileToggle) return;
    const willOpen = !mobileMenu.classList.contains("open");
    if (willOpen) {
      mobileMenu.classList.add("open");
      mobileMenu.setAttribute("aria-hidden", "false");
      mobileToggle.classList.add("open");
      mobileToggle.setAttribute("aria-expanded", "true");
      mobileToggle.setAttribute("aria-label", "Menü schließen");
    } else {
      closeMobileMenu();
    }
  };

  if (mobileToggle && mobileMenu) {
    mobileToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleMobileMenu();
    });

    // Close when clicking outside of mobile menu and toggle button
    document.addEventListener("click", (e) => {
      if (!mobileMenu.contains(e.target) && !mobileToggle.contains(e.target)) {
        closeMobileMenu();
      }
    });

    // Close on Escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && mobileMenu.classList.contains("open")) {
        closeMobileMenu();
        mobileToggle.focus();
      }
    });

    // Close dropdown when a modal trigger inside the menu is clicked (e.g. Persona Manager)
    mobileMenu.querySelectorAll("[data-modal-open]").forEach((btn) => {
      btn.addEventListener("click", () => {
        closeMobileMenu();
      });
    });
  }

  document.querySelectorAll("[data-copy-text]").forEach((btn) => {
    btn.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        btn.click();
      }
    });
    let resetTimer = null;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const text = btn.getAttribute("data-copy-text") || "";
      if (!text) return;
      const labelEl = btn.querySelector("span:not(.icon-mono)");
      const originalLabel = labelEl ? labelEl.textContent : "";
      const showCopiedState = () => {
        if (labelEl) labelEl.textContent = "Kopiert";
        btn.classList.add("copied-success");
        if (resetTimer) clearTimeout(resetTimer);
        resetTimer = setTimeout(() => {
          if (labelEl) labelEl.textContent = originalLabel;
          btn.classList.remove("copied-success");
          resetTimer = null;
        }, 1000);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(showCopiedState).catch(showCopiedState);
      } else {
        const tmp = document.createElement("textarea");
        tmp.value = text;
        tmp.style.position = "fixed";
        tmp.style.opacity = "0";
        document.body.appendChild(tmp);
        tmp.select();
        try {
          document.execCommand("copy");
        } catch (_) {}
        document.body.removeChild(tmp);
        showCopiedState();
      }
    });
  });

  // Hub Header Nav Tab Switcher (instant switch when on overview page, works for desktop and mobile)
  document.querySelectorAll("[data-hub-tab]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const targetId = btn.getAttribute("data-hub-tab");
      const targetPane = document.getElementById(targetId);
      if (targetPane) {
        e.preventDefault();
        document.querySelectorAll("[data-hub-tab]").forEach((b) => {
          if (b.getAttribute("data-hub-tab") === targetId) {
            b.classList.add("active");
          } else {
            b.classList.remove("active");
          }
        });
        const group = targetPane.closest("[data-tab-group]") || document;
        group.querySelectorAll(".tab-pane").forEach((pane) => pane.classList.remove("active"));
        targetPane.classList.add("active");

        const tabParam = targetId.replace("tab-", "");
        const url = new URL(window.location.href);
        url.searchParams.set("tab", tabParam);
        window.history.replaceState({}, "", url.toString());

        closeMobileMenu();
      }
    });
  });

  // Sync tab with URL search parameter on overview page if present
  const currentTabParam = new URLSearchParams(window.location.search).get("tab");
  if (currentTabParam) {
    const pane = document.getElementById(`tab-${currentTabParam}`);
    const navBtn = document.querySelector(`[data-hub-tab="tab-${currentTabParam}"]`);
    if (pane && navBtn) {
      document.querySelectorAll("[data-hub-tab]").forEach((b) => {
        if (b.getAttribute("data-hub-tab") === `tab-${currentTabParam}`) {
          b.classList.add("active");
        } else {
          b.classList.remove("active");
        }
      });
      const group = pane.closest("[data-tab-group]") || document;
      group.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));
      pane.classList.add("active");
    }
  }

  // Dynamic Heart Icon & Color helper for relationship bars
  document.querySelectorAll("[data-relationship-score]").forEach((el) => {
    const score = parseFloat(el.getAttribute("data-relationship-score") || "0");
    const pct = Math.max(0, Math.min(100, ((score + 100) / 200) * 100));
    const fill = el.querySelector(".relationship-fill");
    const heartIcon = el.querySelector(".heart-icon");
    if (fill) {
      fill.style.width = `${pct}%`;
    }
    if (heartIcon) {
      if (score <= -60) {
        heartIcon.textContent = "💔";
        heartIcon.style.color = "#7A1C1C";
      } else if (score < 0) {
        heartIcon.textContent = "❤️‍🩹";
        heartIcon.style.color = "#A93226";
      } else if (score < 50) {
        heartIcon.textContent = "❤️";
        heartIcon.style.color = "#E74C3C";
      } else {
        heartIcon.textContent = "💖";
        heartIcon.style.color = "#FF69B4";
      }
    }
  });

  // Background AI Reply Notification Poller (On-Site Toast when user is NOT in that chat)
  if (document.querySelector(".persona-avatar-btn")) {
    const pollNotifications = async () => {
      try {
        const chatList = document.getElementById("chat-messages-list");
        const chatPane = document.getElementById("chat-pane-messages");
        const isViewingChat =
          chatList && chatPane && chatPane.classList.contains("active") && !document.hidden;
        const activeSessionId = isViewingChat ? chatList.getAttribute("data-session-id") || "" : "";

        const resp = await fetch(
          `/api/chat/notifications?active_session_id=${encodeURIComponent(activeSessionId)}`
        );
        if (!resp.ok) return;
        const data = await resp.json();
        if (Array.isArray(data.notifications)) {
          data.notifications.forEach((n) => window.showAimoToast(n));
        }
      } catch (_) {
        // Ignore transient network errors
      }
    };

    setInterval(pollNotifications, 2500);
    setTimeout(pollNotifications, 600);
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-visibility-toggle]");
    if (!btn || btn.disabled) return;
    const nextState = btn.getAttribute("data-state") === "public" ? "private" : "public";
    const nextTitle = btn.getAttribute(nextState === "public" ? "data-public-title" : "data-private-title") || nextState;
    btn.setAttribute("data-state", nextState);
    btn.setAttribute("aria-pressed", nextState === "public" ? "true" : "false");
    btn.setAttribute("title", nextTitle);
    btn.setAttribute("aria-label", nextTitle);
    const input = btn.closest(".aimo-visibility-toggle-wrap")?.querySelector("input[type='hidden']");
    if (input) {
      input.value = nextState;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });

});
