import { escapeHtml } from "./markdown.js";

export async function refreshSessionMemories(sessionId) {
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

export async function recalculateMemory(sessionId, memoryId, btnEl) {
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

export async function translateMemory(sessionId, memoryId, btnEl) {
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
