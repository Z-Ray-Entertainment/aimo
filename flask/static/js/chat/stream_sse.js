import { renderChatMarkdown } from "./markdown.js";

export function startSSEStream(stream, container, thinkingUI) {
  const ui = thinkingUI || stream.createThinkingBubble(container);
  const meta = stream.getChatMetadata();
  const sidebarSprite = document.getElementById("active-character-sprite");

  return new Promise((resolve) => {
    let rawTokens = "";
    let isCompleted = false;
    let hasErrorHandled = false;

    const handleError = (errMsg, title) => {
      if (isCompleted || hasErrorHandled) return;
      hasErrorHandled = true;
      es.close();
      if (stream.eventSource === es) {
        stream.eventSource = null;
      }
      if (ui?.row && !ui.row.hasAttribute("data-message-idx")) {
        ui.row.remove();
      }
      stream.activeThinkingUI = null;

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

    const es = new EventSource(`/api/chat/${stream.sessionId}/stream?language=${encodeURIComponent(meta.sysLang || "de")}`);
    stream.eventSource = es;

    es.addEventListener("aborted", () => {
      isCompleted = true;
      es.close();
      if (stream.eventSource === es) {
        stream.eventSource = null;
      }
      if (ui?.row) {
        ui.row.remove();
      }
      stream.activeThinkingUI = null;
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
        ui.statusEl.innerHTML = renderChatMarkdown(rawTokens);
      }
      if (container) container.scrollTop = container.scrollHeight;
    });

    es.addEventListener("system_message", (e) => {
      try {
        const sysMsg = JSON.parse(e.data);
        if (!container.querySelector(`[data-message-idx="${sysMsg.message_idx}"]`)) {
          stream.appendSystemMessage(sysMsg, ui?.row);
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
          actionsDiv.innerHTML = stream.buildActionButtonsHtml(data.message_idx, true);
        }
      }
      finalDiv.setAttribute("data-raw-content", finalContent);
      finalDiv.innerHTML = renderChatMarkdown(finalContent);
      ui.bubble.appendChild(finalDiv);

      if (data.sprite_path && sidebarSprite) {
        sidebarSprite.src = `/uploads/${data.sprite_path}`;
      }

      if (typeof data.relationship_value === "number") {
        stream.updateRelationshipUI(
          data.relationship_value,
          data.relationship_tier_name,
          data.relationship_impact
        );
        stream.setTurnRelationshipDebugNotice(
          data.message_idx,
          data.relationship_impact,
          data.relationship_delta
        );
      }

      if (data.suggested_location) {
        stream.showLocationSwitchCountdown(data.suggested_location);
      }

      if (data.cooldown_counter !== undefined && data.cooldown_counter !== null) {
        stream.updateEventCounter(data.cooldown_counter, data.events_enabled);
      }

      setTimeout(() => {
        if (typeof window.refreshSessionMemories === "function") {
          window.refreshSessionMemories();
        }
      }, 3500);

      isCompleted = true;
      es.close();
      if (stream.eventSource === es) {
        stream.eventSource = null;
      }
      stream.activeThinkingUI = null;
      if (container) container.scrollTop = container.scrollHeight;
      resolve();
    });

    es.onerror = () => {
      handleError("Verbindung zum Chat-Stream oder zu Ollama unterbrochen.", "Ollama-Verbindungsfehler");
    };
  });
}
