import {
  appendSystemMessage as renderSystemMessage,
  appendUiNotice as renderUiNotice,
  appendUserBubble as renderUserBubble,
  buildActionButtonsHtml as renderActionButtonsHtml,
  createThinkingBubble as renderThinkingBubble,
  setTurnRelationshipDebugNotice as renderTurnRelationshipDebugNotice,
} from "./message_renderer.js";
import {
  appendImageToGallery as addGalleryTile,
  cancelComfyUIGeneration as doCancelImageGen,
  decrementEventCounterOptimistic as doDecrementEventCounter,
  initImageViewerBindings as bindImageViewers,
  openGridGallery as doOpenGridGallery,
  showLocationSwitchCountdown as doShowLocationCountdown,
  switchLocation as doSwitchLocation,
  triggerComfyUIGeneration as doTriggerImageGen,
  updateEventCounter as doUpdateEventCounter,
} from "./stream_media.js";
import {
  appendRelationshipDebugNotice as doAppendRelDebugNotice,
  initRelationshipDebugToggle as doInitRelDebugToggle,
  recalculateRelationship as doRecalcRelationship,
  setRelationshipDebug as doSetRelDebug,
  updateRelationshipUI as doUpdateRelationshipUI,
} from "./stream_relationship.js";
import { startSSEStream as runSSEStream } from "./stream_sse.js";

export class AimoChatStream {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.countdownTimer = null;
    this.isGeneratingImage = false;
    this.isSending = false;
    this.initRelationshipDebugToggle();
    this.initImageViewerBindings();
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
    return renderActionButtonsHtml(msgIdx, isCharacter, this.getChatMetadata());
  }

  appendImageToGallery(imgUrl, mediaKey) {
    return addGalleryTile(imgUrl, mediaKey);
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

    let tempGalleryTile = null;
    if (localPreviewUrl) {
      tempGalleryTile = this.appendImageToGallery(localPreviewUrl, null);
    }

    const userRow = this.appendUserBubble(messagesList, {
      localized_content: text,
      local_image_url: localPreviewUrl,
    });

    const thinkingUI = this.createThinkingBubble(messagesList, {
      isAnalyzingImage: hasFile,
    });

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
    return renderUserBubble(container, userMsg, this.getChatMetadata());
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
    const ui = renderThinkingBubble(container, this.getChatMetadata(), options);
    if (ui) this.activeThinkingUI = ui;
    return ui;
  }

  startSSEStream(container, thinkingUI) {
    return runSSEStream(this, container, thinkingUI);
  }

  showLocationSwitchCountdown(locationObj) {
    doShowLocationCountdown(this, locationObj);
  }

  appendSystemMessage(msg, insertBeforeEl = null) {
    renderSystemMessage(msg, this.getChatMetadata(), insertBeforeEl);
  }

  decrementEventCounterOptimistic() {
    doDecrementEventCounter();
  }

  updateEventCounter(counter, eventsEnabled) {
    doUpdateEventCounter(counter, eventsEnabled);
  }

  async switchLocation(locationId) {
    return doSwitchLocation(this, locationId);
  }

  async triggerComfyUIGeneration() {
    return doTriggerImageGen(this);
  }

  async cancelComfyUIGeneration() {
    return doCancelImageGen(this);
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
    doUpdateRelationshipUI(relationshipValue, tierName, relationshipImpact);
  }

  appendUiNotice(text) {
    renderUiNotice(text);
  }

  setTurnRelationshipDebugNotice(messageIdx, impact, delta) {
    renderTurnRelationshipDebugNotice(this.getChatMetadata(), messageIdx, impact, delta);
  }

  appendRelationshipDebugNotice(relationshipValue, tierName, impact, delta, evaluatedTurns = null) {
    doAppendRelDebugNotice(this, relationshipValue, tierName, impact, delta, evaluatedTurns);
  }

  setRelationshipDebug(enabled) {
    doSetRelDebug(enabled);
  }

  initRelationshipDebugToggle() {
    doInitRelDebugToggle(this);
  }

  async recalculateRelationship(btn) {
    return doRecalcRelationship(this, btn);
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

  openGridGallery(gridEl, clickedTile) {
    doOpenGridGallery(gridEl, clickedTile);
  }

  initImageViewerBindings() {
    bindImageViewers(this);
  }
}

window.AimoChatStream = AimoChatStream;
