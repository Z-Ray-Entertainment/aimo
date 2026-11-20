import { escapeHtml, renderChatMarkdown } from "./markdown.js";

export function buildActionButtonsHtml(msgIdx, isCharacter, meta) {
  const deleteBtn =
    !isCharacter || msgIdx > 0
      ? `<button type="button" data-action="delete-from" data-msg-idx="${msgIdx}" style="background:none; border:none; color:var(--text-muted); cursor:pointer;" title="Ab hier löschen"><span class="icon-mono">🗑️</span></button>`
      : "";
  const promptDebugBtn =
    isCharacter && meta.isAdmin && msgIdx > 0
      ? `<button type="button" class="btn-prompt-debug" data-action="prompt-debug" data-msg-idx="${msgIdx}" style="background:none; border:none; color:var(--gold-accent); cursor:pointer; font-family:monospace; font-weight:bold; font-size:0.85rem;" title="LLM-Prompt ansehen (Admin)"><span class="icon-mono">{ }</span></button>`
      : "";
  return `
    ${promptDebugBtn}
    <button type="button" data-action="translate-msg" data-msg-idx="${msgIdx}" style="background:none; border:none; color:var(--text-muted); cursor:pointer;" title="Nachricht übersetzen (On-Demand)"><span class="icon-mono">🌐</span></button>
    <button type="button" data-action="edit-msg" data-msg-idx="${msgIdx}" style="background:none; border:none; color:var(--text-muted); cursor:pointer;" title="Nachricht bearbeiten"><span class="icon-mono">✏️</span></button>
    <button type="button" data-action="fork-chat" data-msg-idx="${msgIdx}" style="background:none; border:none; color:var(--text-muted); cursor:pointer;" title="Chat ab hier duplizieren (Fork)"><span class="icon-mono">🌿</span></button>
    ${deleteBtn}
  `;
}

export function appendUserBubble(container, userMsg, meta) {
  if (!container || !userMsg) return null;

  const row = document.createElement("div");
  row.className = "chat-bubble-row user";

  const avatar = document.createElement("img");
  avatar.className = "chat-avatar";
  avatar.src = meta.personaPortrait;
  avatar.alt = meta.personaName;
  avatar.onerror = function () {
    this.src = "/static/img/cover.svg";
  };

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";

  const header = document.createElement("div");
  header.className = "chat-bubble-header";
  header.style.cssText =
    "display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; margin-bottom: 0.25rem; font-size: 0.76rem; color: var(--gold-accent);";
  header.innerHTML = `<strong>${escapeHtml(meta.personaName)}</strong><div class="chat-bubble-actions" style="display: flex; gap: 0.4rem;"></div>`;
  bubble.appendChild(header);

  const imgUrl = userMsg.image_path ? `/uploads/${userMsg.image_path}` : userMsg.local_image_url;
  if (imgUrl) {
    const imgWrap = document.createElement("div");
    imgWrap.className = "chat-uploaded-image-wrap";
    imgWrap.style.marginBottom = "0.45rem";
    imgWrap.innerHTML = `
      <img src="${escapeHtml(imgUrl)}" alt="Upload" style="max-width: 220px; border-radius: 8px; border: 1px solid var(--gold-accent); display: block;">
      <div style="margin-top: 0.25rem;">
        <button type="button" class="btn-eye-alt" title="ALT-Text (Bildbeschreibung) ein-/ausblenden">
          <span class="icon-mono">👁️</span>
        </button>
      </div>
      <div class="chat-image-alt-box" style="display: none;">${escapeHtml(userMsg.image_alt_text || "Bild wird analysiert...")}</div>
    `;
    const eyeBtn = imgWrap.querySelector(".btn-eye-alt");
    const altBox = imgWrap.querySelector(".chat-image-alt-box");
    if (eyeBtn && altBox) {
      eyeBtn.addEventListener("click", () => {
        altBox.style.display = altBox.style.display === "none" ? "block" : "none";
      });
    }
    bubble.appendChild(imgWrap);
  }

  const contentDiv = document.createElement("div");
  contentDiv.className = "chat-markdown";
  contentDiv.setAttribute("data-raw-content", userMsg.localized_content || "");
  contentDiv.innerHTML = renderChatMarkdown(userMsg.localized_content || "");
  bubble.appendChild(contentDiv);

  row.appendChild(avatar);
  row.appendChild(bubble);
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;
  return row;
}

export function createThinkingBubble(container, meta, options = {}) {
  if (!container) return null;
  const isAnalyzingImage = Boolean(options.isAnalyzingImage);

  const row = document.createElement("div");
  row.className = "chat-bubble-row character";

  const avatar = document.createElement("img");
  avatar.className = "chat-avatar";
  avatar.src = meta.characterPortrait;
  avatar.alt = meta.characterName;
  avatar.onerror = function () {
    this.src = "/static/img/cover.svg";
  };

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";

  const header = document.createElement("div");
  header.className = "chat-bubble-header";
  header.style.cssText =
    "display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; margin-bottom: 0.25rem; font-size: 0.76rem; color: var(--gold-accent);";
  header.innerHTML = `<strong>${escapeHtml(meta.characterName)}</strong><div class="chat-bubble-actions" style="display: flex; gap: 0.4rem;"></div>`;
  bubble.appendChild(header);

  const initialLabel = isAnalyzingImage
    ? `${meta.characterName} schaut sich das Bild an`
    : `${meta.characterName} denkt über eine Antwort nach`;

  const thinkingBox = document.createElement("div");
  thinkingBox.className = "ai-thinking-indicator";
  thinkingBox.innerHTML = `
    <span class="thinking-dots" aria-hidden="true"><span></span><span></span><span></span></span>
    <span class="thinking-label">${escapeHtml(initialLabel)}</span>
  `;

  const statusEl = document.createElement("div");
  statusEl.className = "raw-stream-preview";
  statusEl.style.marginTop = "0.35rem";

  bubble.appendChild(thinkingBox);
  bubble.appendChild(statusEl);
  row.appendChild(avatar);
  row.appendChild(bubble);
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;

  return { row, bubble, header, thinkingBox, statusEl, avatar };
}

export function appendSystemMessage(msg, meta, insertBeforeEl = null) {
  const messagesList = document.getElementById("chat-messages-list");
  if (!messagesList || !msg) return;

  const row = document.createElement("div");
  row.className = "chat-system-message-row";
  row.setAttribute("data-message-idx", msg.message_idx);
  row.setAttribute("data-system-type", msg.system_type || "general");

  const icon =
    msg.system_type === "location_change"
      ? msg.metadata && msg.metadata.location_id === null
        ? "🌐"
        : "📍"
      : msg.system_type === "event_trigger"
        ? "⚡"
        : "⚙️";
  const locName = msg.metadata?.location_name || "";
  const eventTitle = msg.metadata?.event_title || "";
  const title =
    msg.system_type === "location_change"
      ? locName
        ? `Ortswechsel: ${locName}`
        : "Ortswechsel"
      : msg.system_type === "event_trigger"
        ? eventTitle
          ? `Ereignis: ${eventTitle}`
          : "Ereignis"
        : "System";

  const systemMsgDiv = document.createElement("div");
  systemMsgDiv.className = `chat-system-message${msg.system_type ? ` system-msg-${msg.system_type}` : ""}`;

  const headerDiv = document.createElement("div");
  headerDiv.className = "chat-system-message-header";

  const badgeDiv = document.createElement("div");
  badgeDiv.className = "chat-system-message-badge";

  const iconSpan = document.createElement("span");
  iconSpan.className = "chat-system-message-icon";
  iconSpan.textContent = icon;

  const titleSpan = document.createElement("span");
  titleSpan.className = "chat-system-message-title";
  titleSpan.textContent = title;

  badgeDiv.appendChild(iconSpan);
  badgeDiv.appendChild(titleSpan);

  const actionsDiv = document.createElement("div");
  actionsDiv.className = "chat-system-message-actions";

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "system-msg-action-btn";
  deleteBtn.title = "Ab hier löschen";
  deleteBtn.setAttribute("data-action", "delete-from");
  deleteBtn.setAttribute("data-msg-idx", String(msg.message_idx));

  const deleteIcon = document.createElement("span");
  deleteIcon.className = "icon-mono";
  deleteIcon.textContent = "🗑️";
  deleteBtn.appendChild(deleteIcon);
  actionsDiv.appendChild(deleteBtn);

  headerDiv.appendChild(badgeDiv);
  headerDiv.appendChild(actionsDiv);

  const contentDiv = document.createElement("div");
  contentDiv.className = "chat-system-message-content";
  let text = msg.localized_content || "";
  if (meta.personaName) {
    text = text.replace(/\{\{user\}\}/gi, meta.personaName);
  }
  if (meta.characterName) {
    text = text.replace(/\{\{char\}\}/gi, meta.characterName);
  }
  contentDiv.textContent = text;

  systemMsgDiv.appendChild(headerDiv);
  systemMsgDiv.appendChild(contentDiv);
  row.appendChild(systemMsgDiv);

  if (insertBeforeEl && insertBeforeEl.parentNode === messagesList) {
    messagesList.insertBefore(row, insertBeforeEl);
  } else {
    messagesList.appendChild(row);
  }
  messagesList.scrollTop = messagesList.scrollHeight;
}

export function appendUiNotice(text) {
  const messagesList = document.getElementById("chat-messages-list");
  if (!messagesList || !text) return;
  const notice = document.createElement("div");
  notice.className = "system-ui-notice";
  notice.textContent = text;
  messagesList.appendChild(notice);
  messagesList.scrollTop = messagesList.scrollHeight;
}

export function setTurnRelationshipDebugNotice(meta, messageIdx, impact, delta) {
  if (!meta.isAdmin && !meta.canDebugRel) return;
  if (messageIdx === undefined || messageIdx === null) return;
  const messagesList = document.getElementById("chat-messages-list");
  if (!messagesList) return;

  const deltaText = typeof delta === "number" ? ` (${delta >= 0 ? "+" : ""}${delta})` : "";
  const text = `[Debug Relationship] ${impact || "neutral"}${deltaText}`;

  let notice = messagesList.querySelector(`.system-ui-notice[data-rel-debug-for="${messageIdx}"]`);
  if (!notice) {
    notice = document.createElement("div");
    notice.className = "system-ui-notice";
    notice.setAttribute("data-rel-debug-for", String(messageIdx));
    const msgRow = messagesList.querySelector(`[data-message-idx="${messageIdx}"]`);
    if (msgRow && msgRow.parentNode === messagesList) {
      msgRow.insertAdjacentElement("afterend", notice);
    } else {
      messagesList.appendChild(notice);
    }
  }
  notice.textContent = text;
}
