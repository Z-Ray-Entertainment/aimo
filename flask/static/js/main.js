window.toggleSecretVisibility = function toggleSecretVisibility(inputId, btnEl) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPassword = input.type === "password";
  input.type = isPassword ? "text" : "password";
  if (btnEl) {
    btnEl.title = isPassword ? window.t("Hide API key") : window.t("Show API key");
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

  let lastInvalidTabSwitchAt = 0;
  document.addEventListener("invalid", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const now = Date.now();
    if (now - lastInvalidTabSwitchAt < 300) return;
    const pane = target.closest(".tab-pane");
    const tabGroup = target.closest("[data-tab-group]");
    if (pane && tabGroup && !pane.classList.contains("active") && pane.id) {
      const tabBtn = tabGroup.querySelector(`[data-tab-target="${CSS.escape(pane.id)}"]`);
      if (tabBtn && !tabBtn.disabled) {
        lastInvalidTabSwitchAt = now;
        tabBtn.click();
        setTimeout(() => {
          try {
            target.focus({ preventScroll: false });
          } catch (_) {}
        }, 0);
        if (typeof window.showToast === "function") {
          window.showToast({
            type: "warning",
            message: window.t("Please fill in all required fields."),
          });
        }
      }
    }
  }, true);
});
