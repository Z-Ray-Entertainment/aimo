import { escapeHtml, renderChatMarkdown } from "./markdown.js";
import { AimoChatStream } from "./stream.js";

const adminPromptCache = {};
let chatStream = null;

function getSessionId() {
  const list = document.getElementById("chat-messages-list");
  return list ? list.dataset.sessionId : "";
}

function toggleImageAltText(msgIdx) {
  const altEl = document.getElementById(`msg-alt-${msgIdx}`);
  if (!altEl) return;
  altEl.style.display = altEl.style.display === "none" ? "block" : "none";
}

async function translateChatMessage(msgIdx, btnEl) {
  const list = document.getElementById("chat-messages-list");
  const sessionId = getSessionId();
  const sysLang =
    list?.getAttribute("data-sys-lang") ||
    (navigator.language || "de").slice(0, 2).toLowerCase();
  const textEl = document.getElementById(`msg-text-${msgIdx}`);
  if (!textEl || !sessionId) return;

  if (btnEl) {
    btnEl.disabled = true;
    btnEl.style.opacity = "0.5";
  }
  try {
    const resp = await fetch(`/api/chat/${sessionId}/messages/${msgIdx}/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_language: sysLang }),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data.translated_text) {
        textEl.setAttribute("data-raw-content", data.translated_text);
        textEl.innerHTML = renderChatMarkdown(data.translated_text);
      }
    }
  } finally {
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.style.opacity = "1";
    }
  }
}

function openEditMessageModal(msgIdx, fallbackText) {
  document.getElementById("edit-msg-idx").value = msgIdx;
  const textEl = document.getElementById(`msg-text-${msgIdx}`);
  const rawText = textEl
    ? (textEl.getAttribute("data-raw-content") ?? textEl.textContent)
    : (fallbackText || "");
  document.getElementById("edit-msg-content").value = rawText;
  window.AimoModals.open("edit-message-modal");
}

async function submitEditMessage(e) {
  e.preventDefault();
  const sessionId = getSessionId();
  const idx = document.getElementById("edit-msg-idx").value;
  const content = document.getElementById("edit-msg-content").value;
  const resp = await fetch(`/api/chat/${sessionId}/messages/${idx}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: content, language: "de" }),
  });
  if (resp.ok) {
    const data = await resp.json();
    const textEl = document.getElementById(`msg-text-${idx}`);
    if (textEl) {
      textEl.setAttribute("data-raw-content", data.localized_content);
      textEl.innerHTML = renderChatMarkdown(data.localized_content);
    }
    window.AimoModals.close("edit-message-modal");
  }
}

async function deleteMessagesFrom(msgIdx) {
  const promptText = window.t(
    "Permanently delete this message and all subsequent messages (including associated memories)?"
  );
  if (!confirm(promptText)) return;
  const sessionId = getSessionId();
  const resp = await fetch(`/api/chat/${sessionId}/messages/${msgIdx}`, {
    method: "DELETE",
  });
  if (resp.ok) {
    window.location.reload();
  }
}

async function forkChatAt(msgIdx) {
  const sessionId = getSessionId();
  const resp = await fetch(`/api/chat/${sessionId}/fork`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fork_point_idx: msgIdx }),
  });
  if (resp.ok) {
    const data = await resp.json();
    window.location.href = `/chat/session/${data.forked_session_id}`;
  }
}

async function manualSwitchLocation(locationId) {
  if (!locationId) return;
  const targetId = locationId === "world" ? null : parseInt(locationId, 10);
  if (targetId !== null && Number.isNaN(targetId)) return;
  if (chatStream) {
    await chatStream.switchLocation(targetId);
  } else {
    const sessionId = getSessionId();
    const resp = await fetch(`/api/chat/${sessionId}/switch-location`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ location_id: targetId }),
    });
    if (resp.ok) {
      window.location.reload();
    }
  }
}

async function refreshSessionMemories() {
  const sessionId = getSessionId();
  if (!sessionId) return;
  try {
    const resp = await fetch(`/api/chat/${sessionId}/memories`);
    if (!resp.ok) return;
    const data = await resp.json();
    const memories = data.memories || [];

    const countEl = document.getElementById("memories-count");
    if (countEl) countEl.textContent = String(memories.length);

    const listEl = document.getElementById("chat-memories-list");
    const emptyEl = document.getElementById("chat-memories-empty");
    if (!listEl) return;

    if (memories.length === 0) {
      listEl.innerHTML = "";
      if (emptyEl) emptyEl.style.display = "block";
      return;
    }

    if (emptyEl) emptyEl.style.display = "none";

    let html = "";
    for (const mem of memories) {
      const tagsStr = (mem.tags || []).join(", ");
      html += `
        <form id="memory-form-${mem.id}" method="POST" action="/chat/session/${sessionId}/memories/${mem.id}/edit" class="aimo-frame" style="padding: 1rem; display: flex; flex-direction: column; gap: 0.6rem;">
          <div style="display: flex; gap: 0.75rem; align-items: center;">
            <input type="text" name="title" value="${escapeHtml(mem.title || "")}" required style="font-weight: 700;">
            <span style="font-size: 0.78rem; color: var(--text-muted); white-space: nowrap;">Nachricht #${mem.message_idx}</span>
          </div>
          <div>
            <label style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(window.t("Tags (Comma-separated for vectorless RAG)"))}</label>
            <input type="text" name="tags" value="${escapeHtml(tagsStr)}">
          </div>
          <div>
            <label style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(window.t("Summary"))}</label>
            <textarea name="summary" rows="3" required>${escapeHtml(mem.summary || "")}</textarea>
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; margin-top: 0.25rem; flex-wrap: wrap;">
            <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
              <button type="button" class="aimo-btn aimo-btn-sm" data-action="recalculate-memory" data-session-id="${sessionId}" data-mem-id="${mem.id}" title="${escapeHtml(window.t("Recalculate memory from associated episode messages"))}">
                <span class="icon-mono">🔄</span> <span>${escapeHtml(window.t("Recalculate"))}</span>
              </button>
              <button type="button" class="aimo-btn aimo-btn-sm" data-action="translate-memory" data-session-id="${sessionId}" data-mem-id="${mem.id}" title="${escapeHtml(window.t("Translate memory in-place to your language"))}">
                <span class="icon-mono">🌐</span> <span>${escapeHtml(window.t("Translate"))}</span>
              </button>
            </div>
            <button type="submit" class="aimo-btn primary aimo-btn-sm"><span class="icon-mono">💾</span> <span>${escapeHtml(window.t("Save"))}</span></button>
          </div>
        </form>
      `;
    }
    listEl.innerHTML = html;
  } catch (err) {
    console.error("Fehler beim Aktualisieren der Erinnerungen:", err);
  }
}

async function openPromptDebugModal(msgIdx) {
  const pre = document.getElementById("prompt-debug-content");
  if (!pre) return;

  pre.textContent = "Lade Prompt aus dem Arbeitsspeicher...";
  if (window.AimoModals) {
    window.AimoModals.open("prompt-debug-modal");
  } else {
    const modal = document.getElementById("prompt-debug-modal");
    if (modal) modal.style.display = "flex";
  }

  if (adminPromptCache[msgIdx]) {
    pre.textContent = adminPromptCache[msgIdx];
    return;
  }

  const sessionId = getSessionId();
  try {
    const resp = await fetch(`/api/chat/${sessionId}/messages/${msgIdx}/prompt`);
    if (!resp.ok) {
      if (resp.status === 404) {
        pre.textContent =
          "Dieser Prompt ist nicht mehr im Arbeitsspeicher vorhanden (Puffer überschritten oder Server wurde neu gestartet).";
      } else if (resp.status === 403) {
        pre.textContent = "Zugriff verweigert: Nur Administratoren dürfen Prompts einsehen.";
      } else {
        pre.textContent = `Fehler beim Abrufen des Prompts (HTTP ${resp.status}).`;
      }
      return;
    }
    const data = await resp.json();
    if (data && data.prompt) {
      adminPromptCache[msgIdx] = data.prompt;
      pre.textContent = data.prompt;
    } else {
      pre.textContent = "Kein Prompt für diese Nachricht im Arbeitsspeicher verfügbar.";
    }
  } catch (err) {
    pre.textContent = `Netzwerkfehler: ${err.message}`;
  }
}

function copyPromptDebugText() {
  const pre = document.getElementById("prompt-debug-content");
  if (!pre || !pre.textContent) return;
  navigator.clipboard.writeText(pre.textContent).then(() => {
    const btn = document.getElementById("copy-prompt-debug-btn");
    if (btn) {
      const orig = btn.textContent;
      btn.textContent = "✓ Kopiert!";
      setTimeout(() => {
        btn.textContent = orig;
      }, 1800);
    }
  });
}

async function recalculateMemory(sessionId, memoryId, btnEl) {
  if (!sessionId || !memoryId) return;
  const form =
    document.getElementById(`memory-form-${memoryId}`) ||
    (btnEl ? btnEl.closest("form") : null);
  if (!form) return;

  const originalBtnHtml = btnEl.innerHTML;
  btnEl.disabled = true;
  btnEl.innerHTML = '<span class="icon-mono">⏳</span> Berechne...';

  const titleInput = form.querySelector('input[name="title"]');
  const tagsInput = form.querySelector('input[name="tags"]');
  const summaryInput = form.querySelector('textarea[name="summary"]');

  try {
    const resp = await fetch(`/api/chat/${sessionId}/memories/${memoryId}/recalculate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || `HTTP ${resp.status}`);
    }

    if (titleInput && data.title) titleInput.value = data.title;
    if (tagsInput && data.tags) {
      tagsInput.value = Array.isArray(data.tags) ? data.tags.join(", ") : data.tags;
    }
    if (summaryInput && data.summary) summaryInput.value = data.summary;

    btnEl.innerHTML = '<span class="icon-mono">✓</span> Neu berechnet!';
    btnEl.style.borderColor = "var(--gold-accent)";
    btnEl.style.color = "var(--gold-accent)";

    setTimeout(() => {
      btnEl.disabled = false;
      btnEl.innerHTML = originalBtnHtml;
      btnEl.style.borderColor = "";
      btnEl.style.color = "";
    }, 3000);
  } catch (err) {
    if (window.showToastError) {
      window.showToastError(err.message, window.t("Recalculation error"));
    } else {
      alert(window.t("Recalculation error:") + " " + err.message);
    }
    btnEl.disabled = false;
    btnEl.innerHTML = originalBtnHtml;
  }
}

async function translateMemory(sessionId, memoryId, btnEl) {
  if (!sessionId || !memoryId) return;
  const form =
    document.getElementById(`memory-form-${memoryId}`) ||
    (btnEl ? btnEl.closest("form") : null);
  if (!form) return;

  const originalBtnHtml = btnEl.innerHTML;
  btnEl.disabled = true;
  btnEl.innerHTML = `<span class="icon-mono">⏳</span> ${escapeHtml(window.t("Translating..."))}`;

  const titleInput = form.querySelector('input[name="title"]');
  const tagsInput = form.querySelector('input[name="tags"]');
  const summaryInput = form.querySelector('textarea[name="summary"]');

  try {
    const resp = await fetch(`/api/chat/${sessionId}/memories/${memoryId}/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || `HTTP ${resp.status}`);
    }

    if (titleInput && data.title) titleInput.value = data.title;
    if (tagsInput && data.tags) {
      tagsInput.value = Array.isArray(data.tags) ? data.tags.join(", ") : data.tags;
    }
    if (summaryInput && data.summary) summaryInput.value = data.summary;

    btnEl.innerHTML = `<span class="icon-mono">✓</span> ${escapeHtml(window.t("Translated!"))}`;
    btnEl.style.borderColor = "var(--gold-accent)";
    btnEl.style.color = "var(--gold-accent)";

    setTimeout(() => {
      btnEl.disabled = false;
      btnEl.innerHTML = originalBtnHtml;
      btnEl.style.borderColor = "";
      btnEl.style.color = "";
    }, 3000);
  } catch (err) {
    if (window.showToastError) {
      window.showToastError(err.message, window.t("Translation error"));
    } else {
      alert(window.t("Translation error:") + " " + err.message);
    }
    btnEl.disabled = false;
    btnEl.innerHTML = originalBtnHtml;
  }
}

function syncSidebarLayout() {
  const mql = window.matchMedia("(max-width: 991px)");
  const sidebar = document.getElementById("chat-pane-sidebar");
  const overlay = document.querySelector(".chat-stage-overlay");
  const layout = document.querySelector(".chat-layout");
  const sidebarTabBtn = document.querySelector('[data-tab-target="chat-pane-sidebar"]');
  const chatTabBtn = document.querySelector('[data-tab-target="chat-pane-messages"]');

  if (!sidebar || !overlay || !layout) return;

  if (mql.matches) {
    if (sidebar.parentElement !== overlay) {
      sidebar.classList.add("tab-pane");
      overlay.appendChild(sidebar);
    }
  } else if (sidebar.parentElement !== layout) {
    const wasActive = sidebar.classList.contains("active");
    sidebar.classList.remove("tab-pane", "active");
    layout.appendChild(sidebar);
    if (sidebarTabBtn) sidebarTabBtn.classList.remove("active");
    if (wasActive && chatTabBtn) {
      chatTabBtn.click();
    }
  }
}

function bindDelegatedActions() {
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    const msgIdx = btn.dataset.msgIdx ? Number(btn.dataset.msgIdx) : null;

    switch (action) {
      case "prompt-debug":
        if (msgIdx !== null) openPromptDebugModal(msgIdx);
        break;
      case "translate-msg":
        if (msgIdx !== null) translateChatMessage(msgIdx, btn);
        break;
      case "edit-msg":
        if (msgIdx !== null) openEditMessageModal(msgIdx);
        break;
      case "fork-chat":
        if (msgIdx !== null) forkChatAt(msgIdx);
        break;
      case "delete-from":
        if (msgIdx !== null) deleteMessagesFrom(msgIdx);
        break;
      case "toggle-alt":
        if (msgIdx !== null) toggleImageAltText(msgIdx);
        break;
      case "generate-image":
        chatStream?.triggerComfyUIGeneration();
        break;
      case "cancel-image":
        chatStream?.cancelComfyUIGeneration();
        break;
      case "regenerate-turn":
        chatStream?.regenerateLastTurn();
        break;
      case "abort-turn":
        chatStream?.abortTurn();
        break;
      case "recalculate-memory":
        recalculateMemory(Number(btn.dataset.sessionId), Number(btn.dataset.memId), btn);
        break;
      case "translate-memory":
        translateMemory(Number(btn.dataset.sessionId), Number(btn.dataset.memId), btn);
        break;
      case "recalculate-rel":
        chatStream?.recalculateRelationship(btn);
        break;
      case "copy-prompt-debug":
        copyPromptDebugText();
        break;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const sessionId = Number(getSessionId());
  if (!sessionId) return;

  document.querySelectorAll(".chat-markdown").forEach((el) => {
    const raw = el.getAttribute("data-raw-content") ?? el.textContent ?? "";
    el.innerHTML = renderChatMarkdown(raw);
  });

  chatStream = new AimoChatStream(sessionId);
  window.chatStream = chatStream;

  const chatForm = document.getElementById("chat-input-form");
  const chatTextarea = document.getElementById("chat-message-textarea");
  if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      chatStream.sendMessage(chatForm);
    });
  }
  if (chatTextarea && chatForm) {
    chatTextarea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatStream.sendMessage(chatForm);
      }
    });
  }

  const uploadInput = document.getElementById("chat-upload-image-input");
  if (uploadInput) {
    uploadInput.addEventListener("change", () => {
      const indicator = document.getElementById("upload-file-indicator");
      if (indicator) {
        indicator.textContent = uploadInput.files[0] ? uploadInput.files[0].name : "";
      }
    });
  }

  const relDebugCheckbox = document.getElementById("toggle-rel-debug-checkbox");
  if (relDebugCheckbox) {
    relDebugCheckbox.addEventListener("change", () => {
      chatStream.setRelationshipDebug(relDebugCheckbox.checked);
    });
  }

  const locationSelect = document.getElementById("chat-location-select");
  if (locationSelect) {
    locationSelect.addEventListener("change", () => {
      manualSwitchLocation(locationSelect.value);
    });
  }

  const editMsgForm = document.getElementById("edit-message-form");
  if (editMsgForm) {
    editMsgForm.addEventListener("submit", submitEditMessage);
  }

  const list = document.getElementById("chat-messages-list");
  if (list) list.scrollTop = list.scrollHeight;

  const menuToggle = document.getElementById("chat-menu-toggle-btn");
  const menuWrapper = document.getElementById("chat-menu-dropdown-wrapper");
  if (menuToggle && menuWrapper) {
    menuToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const isExpanded = menuWrapper.classList.toggle("open");
      menuToggle.setAttribute("aria-expanded", isExpanded ? "true" : "false");
    });
    document.addEventListener("click", (e) => {
      if (!menuWrapper.contains(e.target)) {
        menuWrapper.classList.remove("open");
        menuToggle.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && menuWrapper.classList.contains("open")) {
        menuWrapper.classList.remove("open");
        menuToggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  const memTabBtn = document.querySelector('[data-tab-target="chat-pane-memories"]');
  if (memTabBtn) {
    memTabBtn.addEventListener("click", refreshSessionMemories);
  }

  syncSidebarLayout();
  const mobileMql = window.matchMedia("(max-width: 991px)");
  if (mobileMql.addEventListener) {
    mobileMql.addEventListener("change", syncSidebarLayout);
  } else if (mobileMql.addListener) {
    mobileMql.addListener(syncSidebarLayout);
  }

  bindDelegatedActions();
  chatStream.checkPendingGeneration();

  if (typeof window.initLorebookManager === "function") {
    window.initLorebookManager({
      rootSelector: ".lorebook-manager-root",
      isNewChat: false,
      sessionId: sessionId,
      modalId: "session-add-lorebook-modal",
      countBadgeSelector: "#session-lorebooks-count",
    });
  }
});
