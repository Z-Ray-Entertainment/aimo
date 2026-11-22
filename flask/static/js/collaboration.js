// Reusable Collaboration Manager Component Controller
if (!window.AIMO_COLLAB_LOADED) {
  window.AIMO_COLLAB_LOADED = true;
  // Reusable Collaboration Manager Component Controller
  const initCollaborationManagers = () => {
    document.querySelectorAll(".collaboration-manager-root").forEach((root) => {
      if (root.dataset.initialized) return;
      root.dataset.initialized = "true";

      const hiddenInput = root.querySelector(".collab-tags-hidden-input");
      const tableBody = root.querySelector(".collab-table-body");
      const emptyNotice = root.querySelector(".collab-empty-notice");
      const newTagInput = root.querySelector(".collab-new-tag-input");
      const addBtn = root.querySelector(".add-collab-tag-btn");
      const feedbackMsg = root.querySelector(".collab-feedback-msg");
      const isAuthor = !root.querySelector(".collab-add-box") ? false : true;

      const getTags = () => {
        if (!hiddenInput) return [];
        return hiddenInput.value
          .split(",")
          .map((t) => t.trim().toLowerCase())
          .filter((t) => t.length > 0);
      };

      const setTags = (tags) => {
        const unique = Array.from(new Set(tags));
        if (hiddenInput) {
          hiddenInput.value = unique.join(", ");
        }
        updateUI(unique);
      };

      const showFeedback = (text, isError = true) => {
        if (!feedbackMsg) return;
        feedbackMsg.textContent = text;
        feedbackMsg.style.display = "block";
        feedbackMsg.style.color = isError ? "#ff6b6b" : "#4CAF50";
        setTimeout(() => {
          feedbackMsg.style.display = "none";
        }, 5000);
      };

      const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

      const updateUI = (tags) => {
        if (!tableBody) return;
        tableBody.innerHTML = "";
        if (tags.length === 0) {
          if (emptyNotice) emptyNotice.style.display = "block";
        } else {
          if (emptyNotice) emptyNotice.style.display = "none";
          tags.forEach((tag, idx) => {
            const tr = document.createElement("tr");
            tr.className = "collab-row";
            tr.dataset.tag = tag;
            let actionTd = "";
            if (isAuthor) {
              actionTd = `
                <td style="text-align: right;">
                  <button type="button" class="aimo-btn danger remove-collab-tag-btn" data-tag="${tag}" style="padding: 0.25rem 0.65rem; font-size: 0.78rem;" title="Kollaborator entfernen">
                    <span class="icon-mono">🗑️</span> Entfernen
                  </button>
                </td>
              `;
            }
            tr.innerHTML = `
              <td style="text-align: center; color: var(--text-muted); font-weight: 600;" class="collab-row-idx">${idx + 1}</td>
              <td>
                <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                  <code class="collab-tag-code" style="font-family: monospace; font-size: 0.88rem; background: rgba(0, 0, 0, 0.4); padding: 0.22rem 0.55rem; border-radius: 6px; border: 1px solid var(--border-wood-dark); color: var(--gold-accent); letter-spacing: 0.5px;">${tag}</code>
                  <button type="button" class="aimo-btn copy-collab-tag-btn" data-tag="${tag}" style="padding: 0.2rem 0.45rem; font-size: 0.75rem;" title="Creator-Tag kopieren">
                    <span class="icon-mono">📋</span>
                  </button>
                </div>
              </td>
              <td>
                <span class="aimo-card-badge" style="font-size: 0.78rem; padding: 0.2rem 0.55rem; background: rgba(212, 175, 55, 0.12); border-color: var(--gold-accent);">
                  ✏️ Bearbeiten erlaubt
                </span>
              </td>
              ${actionTd}
            `;
            tableBody.appendChild(tr);
          });
        }
      };

      if (addBtn && newTagInput) {
        const handleAdd = () => {
          const raw = newTagInput.value.trim();
          if (!raw) return;
          const candidates = raw.split(/[\s,]+/).map((s) => s.trim().toLowerCase()).filter(Boolean);
          const currentTags = getTags();
          let addedCount = 0;
          for (const candidate of candidates) {
            if (!UUID_REGEX.test(candidate)) {
              showFeedback(`Ungültiges Format für Creator-Tag: '${candidate}'. Erwartet wird eine 36-stellige UUID.`, true);
              return;
            }
            if (currentTags.includes(candidate)) {
              showFeedback(`Der Creator-Tag '${candidate}' ist bereits vorhanden.`, true);
              return;
            }
            currentTags.push(candidate);
            addedCount++;
          }
          setTags(currentTags);
          newTagInput.value = "";
          showFeedback(`✓ ${addedCount} Creator-Tag(s) hinzugefügt. Klicke auf 'Speichern', um die Änderungen zu sichern.`, false);
        };

        addBtn.addEventListener("click", handleAdd);
        newTagInput.addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            handleAdd();
          }
        });
      }

      root.addEventListener("click", (e) => {
        const removeBtn = e.target.closest(".remove-collab-tag-btn");
        if (removeBtn) {
          const tagToRemove = removeBtn.getAttribute("data-tag");
          if (tagToRemove) {
            const currentTags = getTags().filter((t) => t !== tagToRemove.toLowerCase());
            setTags(currentTags);
            showFeedback("✓ Creator-Tag entfernt. Klicke auf 'Speichern', um die Änderungen zu sichern.", false);
          }
          return;
        }

        const copyBtn = e.target.closest(".copy-collab-tag-btn");
        if (copyBtn) {
          const tagToCopy = copyBtn.getAttribute("data-tag");
          if (tagToCopy && navigator.clipboard) {
            navigator.clipboard.writeText(tagToCopy).then(() => {
              const origIcon = copyBtn.innerHTML;
              copyBtn.innerHTML = '<span class="icon-mono">✓</span>';
              setTimeout(() => {
                copyBtn.innerHTML = origIcon;
              }, 2000);
            });
          }
        }
      });
    });
  };

  initCollaborationManagers();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCollaborationManagers);
  } else {
    initCollaborationManagers();
  }
}
