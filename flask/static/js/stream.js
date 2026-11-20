function escapeHtml(raw) {
  return String(raw || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderInlineMarkdown(escaped) {
  const codePlaceholders = [];
  let text = escaped.replace(/`([^`\n]+)`/g, (_, code) => {
    const idx = codePlaceholders.length;
    codePlaceholders.push(`<code>${code}</code>`);
    return `\x00CODE${idx}\x00`;
  });

  text = text.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/__(.+?)__/g, "<strong>$1</strong>");
  text = text.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  text = text.replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");
  text = text.replace(/~~(.+?)~~/g, "<del>$1</del>");

  text = text.replace(/\x00CODE(\d+)\x00/g, (_, idx) => codePlaceholders[Number(idx)] || "");
  return text;
}

window.renderChatMarkdown = function renderChatMarkdown(rawText) {
  if (!rawText) return "";
  const normalized = String(rawText).replace(/\r\n/g, "\n");

  const fencedBlocks = [];
  const withPlaceholders = normalized.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = fencedBlocks.length;
    fencedBlocks.push(
      `<pre class="md-code-block"><code data-lang="${escapeHtml(lang)}">${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`
    );
    return `\n\x00FENCED${idx}\x00\n`;
  });

  const lines = withPlaceholders.split("\n");
  const htmlParts = [];
  let inUl = false;
  let inOl = false;

  const closeLists = () => {
    if (inUl) {
      htmlParts.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      htmlParts.push("</ol>");
      inOl = false;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    const fencedMatch = trimmed.match(/^\x00FENCED(\d+)\x00$/);
    if (fencedMatch) {
      closeLists();
      htmlParts.push(fencedBlocks[Number(fencedMatch[1])] || "");
      continue;
    }

    if (!trimmed) {
      closeLists();
      continue;
    }

    const headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      closeLists();
      const level = headingMatch[1].length + 1; // h2-h4 inside bubble
      htmlParts.push(`<h${level} class="md-heading">${renderInlineMarkdown(escapeHtml(headingMatch[2]))}</h${level}>`);
      continue;
    }

    const quoteMatch = line.match(/^>\s?(.*)$/);
    if (quoteMatch) {
      closeLists();
      htmlParts.push(`<blockquote class="md-quote">${renderInlineMarkdown(escapeHtml(quoteMatch[1]))}</blockquote>`);
      continue;
    }

    const ulMatch = line.match(/^\s*[-*]\s+(.+)$/);
    if (ulMatch) {
      if (inOl) {
        htmlParts.push("</ol>");
        inOl = false;
      }
      if (!inUl) {
        htmlParts.push('<ul class="md-list">');
        inUl = true;
      }
      htmlParts.push(`<li>${renderInlineMarkdown(escapeHtml(ulMatch[1]))}</li>`);
      continue;
    }

    const olMatch = line.match(/^\s*\d+\.\s+(.+)$/);
    if (olMatch) {
      if (inUl) {
        htmlParts.push("</ul>");
        inUl = false;
      }
      if (!inOl) {
        htmlParts.push('<ol class="md-list">');
        inOl = true;
      }
      htmlParts.push(`<li>${renderInlineMarkdown(escapeHtml(olMatch[1]))}</li>`);
      continue;
    }

    closeLists();
    htmlParts.push(`<p class="md-p">${renderInlineMarkdown(escapeHtml(line))}</p>`);
  }

  closeLists();
  return htmlParts.join("");
};

class AimoChatStream {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.countdownTimer = null;
    this.isGeneratingImage = false;
    this.isSending = false;
    this.initRelationshipDebugToggle();
  }

  setGeneratingUIState(isGenerating) {
    const input = document.getElementById("chat-message-textarea") || document.querySelector("#chat-input-form textarea, #chat-input-form input[name='message']");
    const submitBtn = document.getElementById("chat-send-btn") || document.querySelector("#chat-input-form button[type='submit']");
    const regenBtn = document.getElementById("chat-regenerate-btn");
    const abortBtn = document.getElementById("chat-abort-btn");

    if (isGenerating) {
      if (input) input.disabled = true;
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.style.display = "none";
      }
      if (regenBtn) {
        regenBtn.disabled = true;
        regenBtn.style.display = "none";
      }
      if (abortBtn) {
        abortBtn.style.display = "inline-flex";
      }
    } else {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.style.display = "";
      }
      if (regenBtn) {
        regenBtn.disabled = false;
        regenBtn.style.display = "inline-flex";
      }
      if (abortBtn) {
        abortBtn.style.display = "none";
      }
      if (input && !this.isGeneratingImage) {
        input.disabled = false;
        input.focus();
      }
    }
  }

  getChatMetadata() {
    const list = document.getElementById("chat-messages-list");
    return {
      sysLang: list?.getAttribute("data-sys-lang") || (navigator.language || "de").slice(0, 2).toLowerCase(),
      characterName: list?.getAttribute("data-character-name") || "Charakter",
      characterPortrait: list?.getAttribute("data-character-portrait") || "/static/img/cover.svg",
      personaName: list?.getAttribute("data-persona-name") || "Du",
      personaPortrait: list?.getAttribute("data-persona-portrait") || "/static/img/cover.svg",
      isAdmin: list?.getAttribute("data-is-admin") === "true",
      canDebugRel: list?.getAttribute("data-can-debug-rel") === "true",
    };
  }

  buildActionButtonsHtml(msgIdx, isCharacter) {
    const meta = this.getChatMetadata();
    const deleteBtn =
      !isCharacter || msgIdx > 0
        ? `<button type="button" onclick="deleteMessagesFrom(${msgIdx})" style="background:none; border:none; color:var(--text-muted); cursor:pointer;" title="Ab hier löschen"><span class="icon-mono">🗑️</span></button>`
        : "";
    const promptDebugBtn = (isCharacter && meta.isAdmin && msgIdx > 0)
      ? `<button type="button" class="btn-prompt-debug" onclick="window.openPromptDebugModal(${msgIdx})" style="background:none; border:none; color:var(--gold-accent); cursor:pointer; font-family:monospace; font-weight:bold; font-size:0.85rem;" title="LLM-Prompt ansehen (Admin)"><span class="icon-mono">{ }</span></button>`
      : "";
    return `
      ${promptDebugBtn}
      <button type="button" onclick="window.translateChatMessage(${msgIdx}, this)" style="background:none; border:none; color:var(--text-muted); cursor:pointer;" title="Nachricht übersetzen (On-Demand)"><span class="icon-mono">🌐</span></button>
      <button type="button" onclick="openEditMessageModal(${msgIdx})" style="background:none; border:none; color:var(--text-muted); cursor:pointer;" title="Nachricht bearbeiten"><span class="icon-mono">✏️</span></button>
      <button type="button" onclick="forkChatAt(${msgIdx})" style="background:none; border:none; color:var(--text-muted); cursor:pointer;" title="Chat ab hier duplizieren (Fork)"><span class="icon-mono">🌿</span></button>
      ${deleteBtn}
    `;
  }

  appendImageToGallery(imgUrl, mediaKey) {
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
    tile.className = "card-tile";
    tile.style.minHeight = "180px";
    if (mediaKey) {
      tile.setAttribute("data-media-path", mediaKey);
    }
    tile.innerHTML = `<img src="${escapeHtml(imgUrl)}" alt="Chat Media" style="width: 100%; height: 100%; object-fit: cover;">`;
    grid.appendChild(tile);
    return tile;
  }

  async checkPendingGeneration() {
    const messagesList = document.getElementById("chat-messages-list");
    if (!messagesList || this.isSending) return;

    try {
      const resp = await fetch(`/api/chat/${this.sessionId}/status`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.active) {
        this.isSending = true;
        this.setGeneratingUIState(true);
        const thinkingUI = this.createThinkingBubble(messagesList, {
          isAnalyzingImage: data.status === "analyzing_image",
        });
        await this.startSSEStream(messagesList, thinkingUI);
      }
    } catch (_) {
    } finally {
      this.isSending = false;
      this.activeThinkingUI = null;
      this.setGeneratingUIState(false);
    }
  }

  async sendMessage(formElement) {
    if (this.isSending) return;
    const input = formElement.querySelector("textarea[name='message'], input[name='message']");
    const fileInput = formElement.querySelector("input[type='file'][name='image']");
    const fileIndicator = document.getElementById("upload-file-indicator");
    const messagesList = document.getElementById("chat-messages-list");
    const meta = this.getChatMetadata();

    const text = input ? input.value.trim() : "";
    const hasFile = Boolean(fileInput && fileInput.files && fileInput.files.length > 0);
    if (!text && !hasFile) return;

    this.isSending = true;
    this.setGeneratingUIState(true);

    const selectedFile = hasFile ? fileInput.files[0] : null;
    const localPreviewUrl = selectedFile ? URL.createObjectURL(selectedFile) : null;

    const formData = new FormData();
    formData.append("message", text);
    formData.append("language", meta.sysLang || "de");
    formData.append("stream", "false");
    if (selectedFile) {
      formData.append("image", selectedFile);
    }

    if (input) input.value = "";
    if (fileInput) fileInput.value = "";
    if (fileIndicator) fileIndicator.textContent = "";

    // 1. Nutzernachricht sofort im Chat anzeigen & ggf. Bild sofort in die Galerie einfügen
    let tempGalleryTile = null;
    if (localPreviewUrl) {
      tempGalleryTile = this.appendImageToGallery(localPreviewUrl, null);
    }

    const userRow = this.appendUserBubble(messagesList, {
      localized_content: text,
      local_image_url: localPreviewUrl,
    });

    // 2. Visuelles Feedback sofort anzeigen (bei Bild-Upload zuerst "[char] schaut sich das Bild an")
    const thinkingUI = this.createThinkingBubble(messagesList, {
      isAnalyzingImage: hasFile,
    });

    // 3. Event-Cooldown sofort dynamisch um 1 verringern (optimistisches UI-Update)
    this.decrementEventCounterOptimistic();

    try {
      const prepResp = await fetch(`/api/chat/${this.sessionId}/messages`, {
        method: "POST",
        body: formData,
      });
      const prepData = await prepResp.json();
      if (!prepResp.ok) {
        if (thinkingUI?.row) thinkingUI.row.remove();
        if (userRow) userRow.remove();
        if (tempGalleryTile) tempGalleryTile.remove();
        
        const errStr = String(prepData.error || "");
        if (prepResp.status === 504 || prepData.is_timeout || /timeout|zeitüberschreitung/i.test(errStr)) {
          window.showToastWarning ? window.showToastWarning(errStr || window.t("Timeout while sending."), window.t("Timeout")) : alert(errStr);
        } else if (prepResp.status === 502 || prepData.is_backend_down || /core service unreachable|backend/i.test(errStr)) {
          window.showToastError ? window.showToastError(window.t("Connection to backend (aimo-core) lost."), window.t("Backend connection error")) : alert(window.t("Connection to backend (aimo-core) lost."));
        } else if (/ollama|google\s*ai|gemini|api[- ]?key|llm|provider/i.test(errStr)) {
          window.showToastError ? window.showToastError(errStr || window.t("Connection to AI backend lost."), window.t("AI connection error")) : alert(errStr);
        } else {
          window.showToastError ? window.showToastError(errStr || window.t("Error sending message."), window.t("Error")) : alert(errStr);
        }
        return;
      }

      if (prepData.user_message && userRow) {
        this.upgradeUserBubbleWithServerData(userRow, prepData.user_message, tempGalleryTile);
      }

      if (prepData.system_message) {
        this.appendSystemMessage(prepData.system_message, thinkingUI?.row);
      }
      if (prepData.cooldown_counter !== undefined && prepData.cooldown_counter !== null) {
        this.updateEventCounter(prepData.cooldown_counter, prepData.events_enabled);
      }

      await this.startSSEStream(messagesList, thinkingUI);
    } catch (fetchErr) {
      if (thinkingUI?.row) thinkingUI.row.remove();
      if (userRow) userRow.remove();
      if (tempGalleryTile) tempGalleryTile.remove();
      if (window.showToastError) {
        window.showToastError(window.t("Connection to backend (aimo-core) lost."), window.t("Backend connection error"));
      } else {
        alert(window.t("Connection to backend lost: {error}", { error: fetchErr.message }));
      }
    } finally {
      this.isSending = false;
      this.activeThinkingUI = null;
      this.setGeneratingUIState(false);
    }
  }

  appendUserBubble(container, userMsg) {
    if (!container || !userMsg) return null;
    const meta = this.getChatMetadata();

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
    contentDiv.innerHTML = window.renderChatMarkdown(userMsg.localized_content || "");
    bubble.appendChild(contentDiv);

    row.appendChild(avatar);
    row.appendChild(bubble);
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
    return row;
  }

  upgradeUserBubbleWithServerData(row, serverMsg, tempGalleryTile) {
    if (!row || !serverMsg || serverMsg.message_idx === undefined) return;
    row.setAttribute("data-message-idx", serverMsg.message_idx);
    const contentDiv = row.querySelector(".chat-markdown");
    if (contentDiv) {
      contentDiv.id = `msg-text-${serverMsg.message_idx}`;
    }
    const altBox = row.querySelector(".chat-image-alt-box");
    if (altBox) {
      altBox.id = `msg-alt-${serverMsg.message_idx}`;
      if (serverMsg.image_alt_text) {
        altBox.textContent = serverMsg.image_alt_text;
      }
    }
    if (serverMsg.image_path) {
      const serverImgUrl = `/uploads/${serverMsg.image_path}`;
      const bubbleImg = row.querySelector(".chat-uploaded-image-wrap img");
      if (bubbleImg) {
        bubbleImg.src = serverImgUrl;
      }
      if (tempGalleryTile) {
        tempGalleryTile.setAttribute("data-media-path", serverMsg.image_path);
        const tileImg = tempGalleryTile.querySelector("img");
        if (tileImg) tileImg.src = serverImgUrl;
      } else {
        this.appendImageToGallery(serverImgUrl, serverMsg.image_path);
      }
    }
    const actionsDiv = row.querySelector(".chat-bubble-actions");
    if (actionsDiv) {
      actionsDiv.innerHTML = this.buildActionButtonsHtml(serverMsg.message_idx, false);
    }
  }

  createThinkingBubble(container, options = {}) {
    if (!container) return null;
    const meta = this.getChatMetadata();
    const isAnalyzingImage = Boolean(options.isAnalyzingImage);

    const row = document.createElement("div");
    row.className = "chat-bubble-row character";

    // Character Bubble Icon ist immer das Default Portrait (NICHT das Emotions-Sprite)
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

    const ui = { row, bubble, header, thinkingBox, statusEl, avatar };
    this.activeThinkingUI = ui;
    return ui;
  }

  startSSEStream(container, thinkingUI) {
    const ui = thinkingUI || this.createThinkingBubble(container);
    const meta = this.getChatMetadata();
    const sidebarSprite = document.getElementById("active-character-sprite");

    return new Promise((resolve) => {
      let rawTokens = "";
      let isCompleted = false;
      let hasErrorHandled = false;

      const handleError = (errMsg, title) => {
        if (isCompleted || hasErrorHandled) return;
        hasErrorHandled = true;
        es.close();
        if (this.eventSource === es) {
          this.eventSource = null;
        }
        if (ui?.row && !ui.row.hasAttribute("data-message-idx")) {
          ui.row.remove();
        }
        this.activeThinkingUI = null;

        const errStr = String(errMsg || "");
        if (/timeout|zeitüberschreitung/i.test(errStr)) {
          if (window.showToastWarning) {
            window.showToastWarning(errStr, window.t("Timeout"));
          } else {
            alert(window.t("Timeout: {error}", { error: errStr }));
          }
        } else if (/core service unreachable|backend/i.test(errStr)) {
          if (window.showToastError) {
            window.showToastError(window.t("Connection to backend (aimo-core) lost."), window.t("Backend connection error"));
          } else {
            alert(window.t("Backend connection error"));
          }
        } else {
          if (window.showToastError) {
            window.showToastError(errStr || window.t("Connection to Ollama (or LLMProvider) lost."), title || window.t("Ollama connection error"));
          } else {
            alert(window.t("Ollama connection error: {error}", { error: errStr }));
          }
        }
        resolve();
      };

      const es = new EventSource(`/api/chat/${this.sessionId}/stream?language=${encodeURIComponent(meta.sysLang || "de")}`);
      this.eventSource = es;

      es.addEventListener("aborted", (e) => {
        isCompleted = true;
        es.close();
        if (this.eventSource === es) {
          this.eventSource = null;
        }
        if (ui?.row) {
          ui.row.remove();
        }
        this.activeThinkingUI = null;
        resolve();
      });

      es.addEventListener("error", (e) => {
        let errMessage = "Verbindung zu Ollama unterbrochen.";
        try {
          if (e.data) {
            const data = JSON.parse(e.data);
            if (data.error) errMessage = data.error;
          }
        } catch (_) {}
        handleError(errMessage, "Ollama-Verbindungsfehler");
      });

      es.addEventListener("image_analyzed", (e) => {
        try {
          const data = JSON.parse(e.data);
          const label = ui.thinkingBox?.querySelector(".thinking-label");
          if (label) {
            label.textContent = `${meta.characterName} denkt über eine Antwort nach`;
          }
          if (data.user_message_idx !== undefined) {
            const altEl = document.getElementById(`msg-alt-${data.user_message_idx}`);
            if (altEl) {
              altEl.textContent = data.image_alt_text || "Keine Bildbeschreibung verfügbar.";
            }
          }
        } catch (_) {}
      });

      es.addEventListener("token", (e) => {
        const data = JSON.parse(e.data);
        rawTokens += data.token || "";
        const label = ui.thinkingBox?.querySelector(".thinking-label");
        if (label && !rawTokens.trim()) {
          label.textContent = `${meta.characterName} denkt über eine Antwort nach`;
        } else if (label) {
          label.textContent = `${meta.characterName} antwortet`;
        }
        if (ui.statusEl) {
          ui.statusEl.innerHTML = window.renderChatMarkdown(rawTokens);
        }
        if (container) container.scrollTop = container.scrollHeight;
      });

      es.addEventListener("system_message", (e) => {
        try {
          const sysMsg = JSON.parse(e.data);
          if (!container.querySelector(`[data-message-idx="${sysMsg.message_idx}"]`)) {
            this.appendSystemMessage(sysMsg, ui?.row);
          }
        } catch (_) {}
      });

      es.addEventListener("generation_done", () => {
        const label = ui.thinkingBox?.querySelector(".thinking-label");
        if (label) {
          label.textContent = `${meta.characterName} ordnet Stimmung & Szene ein`;
        }
      });

      es.addEventListener("message_complete", (e) => {
        const data = JSON.parse(e.data);

        if (data.notification_id) {
          fetch(`/api/chat/notifications/${encodeURIComponent(data.notification_id)}/ack`, {
            method: "POST",
          }).catch(() => {});
        }

        if (ui.thinkingBox) ui.thinkingBox.remove();
        if (ui.statusEl) ui.statusEl.remove();

        if (data.prompt && data.message_idx !== undefined) {
          window._adminPromptCache = window._adminPromptCache || {};
          window._adminPromptCache[data.message_idx] = data.prompt;
        }

        const finalContent = data.localized_content || data.english_content || "";
        const finalDiv = document.createElement("div");
        finalDiv.className = "chat-markdown";
        if (data.message_idx !== undefined) {
          ui.row.setAttribute("data-message-idx", data.message_idx);
          finalDiv.id = `msg-text-${data.message_idx}`;
          const actionsDiv = ui.header?.querySelector(".chat-bubble-actions");
          if (actionsDiv) {
            actionsDiv.innerHTML = this.buildActionButtonsHtml(data.message_idx, true);
          }
        }
        finalDiv.setAttribute("data-raw-content", finalContent);
        finalDiv.innerHTML = window.renderChatMarkdown(finalContent);
        ui.bubble.appendChild(finalDiv);

        // Nur das große Charakter-Sprite in der rechten Seitenleiste aktualisieren, NICHT das Chat-Bubble-Icon
        if (data.sprite_path && sidebarSprite) {
          sidebarSprite.src = `/uploads/${data.sprite_path}`;
        }

        if (typeof data.relationship_value === "number") {
          this.updateRelationshipUI(
            data.relationship_value,
            data.relationship_tier_name,
            data.relationship_impact
          );
          this.setTurnRelationshipDebugNotice(
            data.message_idx,
            data.relationship_impact,
            data.relationship_delta
          );
        }

        if (data.suggested_location) {
          this.showLocationSwitchCountdown(data.suggested_location);
        }

        if (data.cooldown_counter !== undefined && data.cooldown_counter !== null) {
          this.updateEventCounter(data.cooldown_counter, data.events_enabled);
        }

        setTimeout(() => {
          if (typeof window.refreshSessionMemories === "function") {
            window.refreshSessionMemories();
          }
        }, 3500);

        isCompleted = true;
        es.close();
        if (this.eventSource === es) {
          this.eventSource = null;
        }
        this.activeThinkingUI = null;
        if (container) container.scrollTop = container.scrollHeight;
        resolve();
      });

      es.onerror = () => {
        handleError("Verbindung zum Chat-Stream oder zu Ollama unterbrochen.", "Ollama-Verbindungsfehler");
      };
    });
  }

  showLocationSwitchCountdown(locationObj) {
    const bannerContainer = document.getElementById("location-switch-container");
    if (!bannerContainer) return;

    if (this.countdownTimer) {
      clearInterval(this.countdownTimer);
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

    this.countdownTimer = setInterval(() => {
      if (isPaused) return;
      remaining -= 1;
      if (fillEl) {
        fillEl.style.width = `${(remaining / 60) * 100}%`;
      }
      if (remaining <= 0) {
        clearInterval(this.countdownTimer);
        bannerContainer.innerHTML = "";
      }
    }, 1000);

    document.getElementById("loc-confirm-no")?.addEventListener("click", () => {
      clearInterval(this.countdownTimer);
      bannerContainer.innerHTML = "";
    });

    document.getElementById("loc-confirm-yes")?.addEventListener("click", async () => {
      clearInterval(this.countdownTimer);
      bannerContainer.innerHTML = "";
      await this.switchLocation(locationObj.id);
    });
  }

  appendSystemMessage(msg, insertBeforeEl = null) {
    const messagesList = document.getElementById("chat-messages-list");
    if (!messagesList || !msg) return;

    const row = document.createElement("div");
    row.className = "chat-system-message-row";
    row.setAttribute("data-message-idx", msg.message_idx);
    row.setAttribute("data-system-type", msg.system_type || "general");

    const icon = msg.system_type === "location_change"
      ? (msg.metadata && msg.metadata.location_id === null ? "🌐" : "📍")
      : (msg.system_type === "event_trigger" ? "⚡" : "⚙️");
    const locName = msg.metadata?.location_name || "";
    const eventTitle = msg.metadata?.event_title || "";
    const title = msg.system_type === "location_change"
      ? (locName ? `Ortswechsel: ${locName}` : "Ortswechsel")
      : (msg.system_type === "event_trigger" ? (eventTitle ? `Ereignis: ${eventTitle}` : "Ereignis") : "System");

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
    deleteBtn.setAttribute("onclick", `deleteMessagesFrom(${msg.message_idx})`);

    const deleteIcon = document.createElement("span");
    deleteIcon.className = "icon-mono";
    deleteIcon.textContent = "🗑️";
    deleteBtn.appendChild(deleteIcon);
    actionsDiv.appendChild(deleteBtn);

    headerDiv.appendChild(badgeDiv);
    headerDiv.appendChild(actionsDiv);

    const contentDiv = document.createElement("div");
    contentDiv.className = "chat-system-message-content";
    const meta = this.getChatMetadata();
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

  decrementEventCounterOptimistic() {
    const statusEl = document.getElementById("admin-event-counter-status");
    const valEl = document.getElementById("admin-event-counter-val");
    if (!statusEl) return;
    const eventsToggle = document.querySelector(".chat-sidebar-events-toggle input[type='checkbox']");
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

  updateEventCounter(counter, eventsEnabled) {
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

  async switchLocation(locationId) {
    if (locationId === undefined) return null;
    const resp = await fetch(`/api/chat/${this.sessionId}/switch-location`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ location_id: locationId }),
    });
    const resData = await resp.json().catch(() => ({}));
    if (resp.ok) {
      if (resData.system_message) {
        this.appendSystemMessage(resData.system_message);
      } else if (resData.ui_notice) {
        this.appendUiNotice(resData.ui_notice);
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
      return resData;
    } else {
      const errStr = resData.error || "Fehler beim Wechseln des Ortes.";
      window.showToastError ? window.showToastError(errStr) : alert(errStr);
    }
    return null;
  }

  async triggerComfyUIGeneration() {
    if (this.isGeneratingImage) return;
    this.isGeneratingImage = true;

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
    notice.textContent = "Bild wird generiert...";
    if (messagesList) {
      messagesList.appendChild(notice);
      messagesList.scrollTop = messagesList.scrollHeight;
    }

    try {
      const resp = await fetch(`/api/chat/${this.sessionId}/generate-image`, {
        method: "POST",
      });
      const data = await resp.json();
      if (resp.ok && data.image_path) {
        notice.innerHTML = `<img src="/uploads/${data.image_path}" alt="Generierte Szene" style="max-width:320px; border-radius:10px; border:2px solid var(--gold-accent); margin-top:0.4rem;">`;
        this.appendImageToGallery(`/uploads/${data.image_path}`, data.image_path);
      } else {
        notice.textContent = data.error || "Bildgenerierung abgebrochen oder fehlgeschlagen.";
      }
    } finally {
      this.isGeneratingImage = false;
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

  async cancelComfyUIGeneration() {
    await fetch(`/api/chat/${this.sessionId}/cancel-image`, { method: "POST" });
    this.isGeneratingImage = false;
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

  async abortTurn() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    if (this.activeThinkingUI?.row) {
      this.activeThinkingUI.row.remove();
      this.activeThinkingUI = null;
    }

    try {
      await fetch(`/api/chat/${this.sessionId}/abort`, {
        method: "POST",
      });
    } catch (_) {}

    this.isSending = false;
    this.activeThinkingUI = null;
    this.setGeneratingUIState(false);
  }

  updateRelationshipUI(relationshipValue, tierName, relationshipImpact) {
    const relLabel = document.getElementById("rel-score-label");
    if (relLabel && tierName) {
      relLabel.textContent = tierName;
    }
    const galleryRelLabel = document.getElementById("gallery-rel-tier-label");
    if (galleryRelLabel && tierName) {
      galleryRelLabel.textContent = tierName;
    }
    const relWrap = document.querySelector(".relationship-bar-wrap[data-relationship-score]");
    if (!relWrap) return;

    relWrap.setAttribute("data-relationship-score", String(relationshipValue));
    const pct = Math.max(0, Math.min(100, ((relationshipValue + 100) / 200) * 100));
    const fill = relWrap.querySelector(".relationship-fill");
    if (fill) fill.style.width = `${pct}%`;

    const heartIcon = relWrap.querySelector(".heart-icon");
    if (heartIcon) {
      const score = relationshipValue;
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

    const pulseClassMap = {
      positive: "relationship-pulse-positive",
      very_positive: "relationship-pulse-positive",
      negative: "relationship-pulse-negative",
      very_negative: "relationship-pulse-negative",
    };
    const pulseClass = pulseClassMap[relationshipImpact];
    if (pulseClass) {
      relWrap.classList.remove("relationship-pulse-positive", "relationship-pulse-negative");
      void relWrap.offsetWidth;
      relWrap.classList.add(pulseClass);
      relWrap.addEventListener(
        "animationend",
        () => relWrap.classList.remove(pulseClass),
        { once: true }
      );
    }
  }

  appendUiNotice(text) {
    const messagesList = document.getElementById("chat-messages-list");
    if (!messagesList || !text) return;
    const notice = document.createElement("div");
    notice.className = "system-ui-notice";
    notice.textContent = text;
    messagesList.appendChild(notice);
    messagesList.scrollTop = messagesList.scrollHeight;
  }

  setTurnRelationshipDebugNotice(messageIdx, impact, delta) {
    const meta = this.getChatMetadata();
    if (!meta.isAdmin && !meta.canDebugRel) return;
    if (messageIdx === undefined || messageIdx === null) return;
    const messagesList = document.getElementById("chat-messages-list");
    if (!messagesList) return;

    const deltaText =
      typeof delta === "number" ? ` (${delta >= 0 ? "+" : ""}${delta})` : "";
    const text = `[Debug Relationship] ${impact || "neutral"}${deltaText}`;

    let notice = messagesList.querySelector(
      `.system-ui-notice[data-rel-debug-for="${messageIdx}"]`
    );
    if (!notice) {
      notice = document.createElement("div");
      notice.className = "system-ui-notice";
      notice.setAttribute("data-rel-debug-for", String(messageIdx));
      const msgRow = messagesList.querySelector(
        `[data-message-idx="${messageIdx}"]`
      );
      if (msgRow && msgRow.parentNode === messagesList) {
        msgRow.insertAdjacentElement("afterend", notice);
      } else {
        messagesList.appendChild(notice);
      }
    }
    notice.textContent = text;
  }

  appendRelationshipDebugNotice(relationshipValue, tierName, impact, delta, evaluatedTurns = null) {
    if (!this.getChatMetadata().isAdmin) return;
    if (typeof relationshipValue !== "number") return;
    const deltaText =
      typeof delta === "number" ? `${delta >= 0 ? "+" : ""}${delta}` : "?";
    const prefix =
      typeof evaluatedTurns === "number"
        ? `[Debug Relationship Recalc (${evaluatedTurns} turns)]`
        : "[Debug Relationship]";
    const impactLabel = impact || "neutral";
    const tierLabel = tierName || "";
    this.appendUiNotice(
      `${prefix} ${impactLabel} (${deltaText}) → ${relationshipValue} (${tierLabel})`
    );
  }

  setRelationshipDebug(enabled) {
    const messagesList = document.getElementById("chat-messages-list");
    const checkbox = document.getElementById("toggle-rel-debug-checkbox");
    if (messagesList) {
      messagesList.classList.toggle("show-rel-debug", Boolean(enabled));
    }
    if (checkbox) {
      checkbox.checked = Boolean(enabled);
    }
    try {
      localStorage.setItem("aimo_rel_debug", enabled ? "1" : "0");
    } catch (_) {}
  }

  initRelationshipDebugToggle() {
    const meta = this.getChatMetadata();
    if (!meta.isAdmin && !meta.canDebugRel) return;
    let enabled = false;
    try {
      enabled = localStorage.getItem("aimo_rel_debug") === "1";
    } catch (_) {}
    this.setRelationshipDebug(enabled);
  }

  async recalculateRelationship(btn) {
    if (this.isSending || this.isGeneratingImage) return;
    const origHtml = window.setButtonLoading ? window.setButtonLoading(btn, "⏳") : btn?.innerHTML;
    if (btn) btn.disabled = true;

    try {
      const resp = await fetch(`/api/chat/${this.sessionId}/recalculate-relationship`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: this.getChatMetadata().sysLang }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const msg = data.error || window.t("Failed to recalculate relationship.");
        window.showToastError ? window.showToastError(msg, window.t("Error")) : alert(msg);
        return;
      }
      if (Array.isArray(data.turn_results)) {
        data.turn_results.forEach((turn) => {
          this.setTurnRelationshipDebugNotice(turn.message_idx, turn.impact, turn.delta);
        });
      }
      if (typeof data.relationship_value === "number") {
        this.updateRelationshipUI(
          data.relationship_value,
          data.relationship_tier_name,
          data.relationship_impact
        );
        this.appendRelationshipDebugNotice(
          data.relationship_value,
          data.relationship_tier_name,
          data.relationship_impact,
          data.relationship_delta,
          data.evaluated_turns
        );
      }
    } catch (err) {
      const msg = window.t("Connection error: {error}", { error: err.message });
      window.showToastError ? window.showToastError(msg, window.t("Error")) : alert(msg);
    } finally {
      if (window.resetButtonLoading && btn) {
        window.resetButtonLoading(btn, origHtml);
      } else if (btn) {
        btn.disabled = false;
      }
    }
  }

  async regenerateLastTurn() {
    if (this.isSending || this.isGeneratingImage) return;
    this.isSending = true;

    const messagesList = document.getElementById("chat-messages-list");
    this.setGeneratingUIState(true);

    let thinkingUI = null;

    try {
      const resp = await fetch(`/api/chat/${this.sessionId}/regenerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: this.getChatMetadata().sysLang }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        const errStr = String(data.error || "");
        if (resp.status === 504 || data.is_timeout || /timeout|zeitüberschreitung/i.test(errStr)) {
          window.showToastWarning ? window.showToastWarning(errStr || window.t("Timeout while regenerating."), window.t("Timeout")) : alert(errStr);
        } else if (resp.status === 502 || data.is_backend_down || /core service unreachable|backend/i.test(errStr)) {
          window.showToastError ? window.showToastError(window.t("Connection to backend (aimo-core) lost."), window.t("Backend connection error")) : alert(window.t("Backend connection error"));
        } else {
          window.showToastError ? window.showToastError(errStr || window.t("Error while regenerating."), window.t("Ollama error")) : alert(errStr);
        }
        return;
      }

      if (data.deleted_message_idx !== undefined && data.deleted_message_idx !== null) {
        const deletedRow = messagesList?.querySelector(`[data-message-idx="${data.deleted_message_idx}"]`);
        if (deletedRow) {
          deletedRow.remove();
        }
      }

      thinkingUI = this.createThinkingBubble(messagesList);
      await this.startSSEStream(messagesList, thinkingUI);
    } catch (err) {
      if (thinkingUI?.row) thinkingUI.row.remove();
      if (/failed to fetch|network/i.test(err.message)) {
        window.showToastError ? window.showToastError(window.t("Connection to backend (aimo-core) lost."), window.t("Backend connection error")) : alert(window.t("Backend connection error"));
      } else {
        window.showToastError ? window.showToastError(window.t("Connection error: {error}", { error: err.message }), window.t("Ollama connection error")) : alert(window.t("Connection error: {error}", { error: err.message }));
      }
    } finally {
      this.isSending = false;
      this.activeThinkingUI = null;
      this.setGeneratingUIState(false);
    }
  }
}

window.AimoChatStream = AimoChatStream;
