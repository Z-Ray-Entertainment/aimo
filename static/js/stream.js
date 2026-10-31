class AimoChatStream {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.countdownTimer = null;
    this.isGeneratingImage = false;
  }

  async sendMessage(formElement) {
    const input = formElement.querySelector("textarea[name='message'], input[name='message']");
    const fileInput = formElement.querySelector("input[type='file'][name='image']");
    const submitBtn = formElement.querySelector("button[type='submit']");
    const messagesList = document.getElementById("chat-messages-list");

    const text = input ? input.value.trim() : "";
    const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
    if (!text && !hasFile) return;

    if (input) input.disabled = true;
    if (submitBtn) submitBtn.disabled = true;

    const formData = new FormData();
    formData.append("message", text);
    formData.append("language", "de");
    formData.append("stream", "false");
    if (hasFile) {
      formData.append("image", fileInput.files[0]);
    }

    if (input) input.value = "";
    if (fileInput) fileInput.value = "";

    try {
      const prepResp = await fetch(`/api/chat/${this.sessionId}/messages`, {
        method: "POST",
        body: formData,
      });
      const prepData = await prepResp.json();
      if (!prepResp.ok) {
        alert(prepData.error || "Fehler beim Senden der Nachricht.");
        return;
      }

      this.appendUserBubble(messagesList, prepData.user_message);
      await this.startSSEStream(messagesList);
    } finally {
      if (!this.isGeneratingImage) {
        if (input) input.disabled = false;
        if (submitBtn) submitBtn.disabled = false;
        if (input) input.focus();
      }
    }
  }

  appendUserBubble(container, userMsg) {
    if (!container || !userMsg) return;
    const row = document.createElement("div");
    row.className = "chat-bubble-row user";
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    bubble.textContent = userMsg.localized_content || "";
    row.appendChild(bubble);
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
  }

  startSSEStream(container) {
    return new Promise((resolve) => {
      const row = document.createElement("div");
      row.className = "chat-bubble-row character";

      const avatar = document.createElement("img");
      avatar.className = "chat-avatar";
      const defaultSprite = document.getElementById("active-character-sprite");
      avatar.src = defaultSprite ? defaultSprite.src : "/static/img/cover.svg";

      const bubble = document.createElement("div");
      bubble.className = "chat-bubble";

      const statusEl = document.createElement("div");
      statusEl.className = "raw-stream-preview";
      statusEl.textContent = "Denkt nach...";

      bubble.appendChild(statusEl);
      row.appendChild(avatar);
      row.appendChild(bubble);
      container.appendChild(row);
      container.scrollTop = container.scrollHeight;

      let rawTokens = "";
      const es = new EventSource(`/api/chat/${this.sessionId}/stream?language=de`);

      es.addEventListener("token", (e) => {
        const data = JSON.parse(e.data);
        rawTokens += data.token || "";
        statusEl.textContent = rawTokens;
        container.scrollTop = container.scrollHeight;
      });

      es.addEventListener("generation_done", () => {
        const spinner = document.createElement("div");
        spinner.className = "translation-spinner";
        spinner.style.fontSize = "0.8rem";
        spinner.style.color = "var(--gold-accent)";
        spinner.style.marginTop = "0.35rem";
        spinner.textContent = "⏳ Übersetze ins Deutsche...";
        bubble.appendChild(spinner);
      });

      es.addEventListener("message_complete", (e) => {
        const data = JSON.parse(e.data);
        bubble.innerHTML = "";
        const finalP = document.createElement("p");
        finalP.textContent = data.localized_content || data.english_content;
        bubble.appendChild(finalP);

        if (data.sprite_path) {
          const spriteUrl = `/uploads/${data.sprite_path}`;
          avatar.src = spriteUrl;
          if (defaultSprite) defaultSprite.src = spriteUrl;
        }

        if (data.suggested_location) {
          this.showLocationSwitchCountdown(data.suggested_location);
        }

        es.close();
        container.scrollTop = container.scrollHeight;
        resolve();
      });

      es.onerror = () => {
        es.close();
        resolve();
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
      <div class="location-prompt-banner">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:1rem;">
          <span>Zu <strong>${locationObj.name}</strong> wechseln?</span>
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
    const fillEl = document.getElementById("loc-countdown-fill");

    this.countdownTimer = setInterval(() => {
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
      const resp = await fetch(`/api/chat/${this.sessionId}/switch-location`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ location_id: locationObj.id }),
      });
      const resData = await resp.json();
      if (resp.ok) {
        const messagesList = document.getElementById("chat-messages-list");
        if (messagesList && resData.ui_notice) {
          const notice = document.createElement("div");
          notice.className = "system-ui-notice";
          notice.textContent = resData.ui_notice;
          messagesList.appendChild(notice);
          messagesList.scrollTop = messagesList.scrollHeight;
        }
        const stage = document.getElementById("chat-main-stage");
        if (stage && resData.location?.background_image_path) {
          stage.style.backgroundImage = `url('/uploads/${resData.location.background_image_path}')`;
        }
      }
    });
  }

  async triggerComfyUIGeneration() {
    if (this.isGeneratingImage) return;
    this.isGeneratingImage = true;

    const input = document.querySelector("#chat-input-form textarea, #chat-input-form input[name='message']");
    const submitBtn = document.querySelector("#chat-input-form button[type='submit']");
    const cancelBtn = document.getElementById("cancel-image-gen-btn");
    const messagesList = document.getElementById("chat-messages-list");

    if (input) input.disabled = true;
    if (submitBtn) submitBtn.disabled = true;
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
      } else {
        notice.textContent = data.error || "Bildgenerierung abgebrochen oder fehlgeschlagen.";
      }
    } finally {
      this.isGeneratingImage = false;
      if (input) input.disabled = false;
      if (submitBtn) submitBtn.disabled = false;
      if (cancelBtn) cancelBtn.style.display = "none";
    }
  }

  async cancelComfyUIGeneration() {
    await fetch(`/api/chat/${this.sessionId}/cancel-image`, { method: "POST" });
    this.isGeneratingImage = false;
    const input = document.querySelector("#chat-input-form textarea, #chat-input-form input[name='message']");
    const submitBtn = document.querySelector("#chat-input-form button[type='submit']");
    const cancelBtn = document.getElementById("cancel-image-gen-btn");
    if (input) input.disabled = false;
    if (submitBtn) submitBtn.disabled = false;
    if (cancelBtn) cancelBtn.style.display = "none";
  }
}

window.AimoChatStream = AimoChatStream;
