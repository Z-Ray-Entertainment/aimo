/**
 * AIMO Reusable Lorebook Manager
 * Handles interactive lorebook toggling, custom addition, deletion,
 * search filtering, and live synchronization with WorldInfo selection.
 */
(function () {
  "use strict";

  function sortListAlphabetically(container) {
    if (!container) return;
    const items = Array.from(container.querySelectorAll(".lorebook-list-item"));
    items.sort((a, b) => {
      const nameA = (a.getAttribute("data-name") || "").toLowerCase();
      const nameB = (b.getAttribute("data-name") || "").toLowerCase();
      return nameA.localeCompare(nameB);
    });
    items.forEach((item) => container.appendChild(item));
  }

  function updateCountBadge(root, badgeSelector) {
    if (!badgeSelector) return;
    const badge = document.querySelector(badgeSelector);
    if (!badge) return;

    let activeCount = 0;
    root.querySelectorAll(".lorebook-toggle-input").forEach((inp) => {
      if (inp.checked) activeCount++;
    });
    badge.textContent = String(activeCount);
  }

  function updateEmptyNotices(root) {
    const defContainer = root.querySelector("#default-lorebooks-list");
    const defEmpty = root.querySelector("#default-lorebooks-empty");
    if (defContainer && defEmpty) {
      const count = defContainer.querySelectorAll(".lorebook-list-item").length;
      defEmpty.style.display = count === 0 ? "" : "none";
    }

    const custContainer = root.querySelector("#custom-lorebooks-list");
    const custEmpty = root.querySelector("#custom-lorebooks-empty");
    if (custContainer && custEmpty) {
      const count = custContainer.querySelectorAll(".lorebook-list-item").length;
      custEmpty.style.display = count === 0 ? "" : "none";
    }
  }

  function createLorebookRowHtml(lb, type) {
    const isCustom = type === "custom";
    const sourceLabel = isCustom ? "Benutzerdefiniert" : (lb.source || "Welt");
    const tagsArr = Array.isArray(lb.tags) ? lb.tags : (lb.tags ? lb.tags.split(",") : []);
    const visibleTags = tagsArr.slice(0, 4);
    const extraTagsCount = tagsArr.length > 4 ? tagsArr.length - 4 : 0;

    let tagsHtml = `<span style="font-size: 0.75rem; color: var(--gold-accent);">${lb.entry_count || 0} Einträge</span>`;
    visibleTags.forEach((t) => {
      if (t.trim()) {
        tagsHtml += `<span style="font-size: 0.72rem; padding: 0.1rem 0.4rem; border: 1px solid var(--border-wood); border-radius: 8px; color: var(--text-muted);">#${t.trim()}</span>`;
      }
    });
    if (extraTagsCount > 0) {
      tagsHtml += `<span style="font-size: 0.72rem; color: var(--text-muted);">+${extraTagsCount}</span>`;
    }

    const descHtml = lb.description
      ? `<p style="margin: 0.2rem 0 0.4rem 0; font-size: 0.84rem; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${lb.description}</p>`
      : "";

    const deleteBtnHtml = isCustom
      ? `<button type="button" class="aimo-btn danger remove-custom-lorebook-btn" data-lorebook-id="${lb.id}" title="Lorebook aus Chat entfernen">
           <span class="icon-mono">🗑️</span>
         </button>`
      : "";

    return `
      <div class="lorebook-list-item" data-lorebook-id="${lb.id}" data-name="${(lb.name || '').toLowerCase()}" data-source="${sourceLabel}">
        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.25rem; flex-wrap: wrap;">
            <span style="font-weight: 700; color: var(--text-color); font-size: 0.95rem;">
              <span class="icon-mono">📜</span> ${lb.name}
            </span>
            <span class="aimo-card-badge" style="font-size: 0.72rem; padding: 0.15rem 0.5rem;">
              ${sourceLabel}
            </span>
          </div>
          ${descHtml}
          <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
            ${tagsHtml}
          </div>
        </div>
        <div class="lorebook-item-actions-overlay">
          <label class="aimo-switch" title="Lorebook deaktivieren/aktivieren">
            <input type="checkbox" class="lorebook-toggle-input" data-lorebook-id="${lb.id}" checked>
            <span class="aimo-switch-slider"></span>
          </label>
          ${deleteBtnHtml}
        </div>
      </div>
    `;
  }

  function initLorebookManager(options) {
    const root = document.querySelector(options.rootSelector || ".lorebook-manager-root");
    if (!root) return;

    const isNewChat = root.getAttribute("data-is-new-chat") === "true" || !!options.isNewChat;
    const sessionId = options.sessionId || root.getAttribute("data-session-id");
    const modalId = options.modalId || root.getAttribute("data-modal-id") || "chat-add-lorebook-modal";
    const modalEl = document.getElementById(modalId);
    const countBadgeSelector = options.countBadgeSelector;
    const hiddenInputsWrap = document.getElementById("new-chat-lorebook-hidden-inputs");
    const worldinfoSelect = options.worldinfoSelectId ? document.querySelector(options.worldinfoSelectId) : document.querySelector("select[name='worldinfo_id']");
    const worldinfoLorebooksMap = options.worldinfoLorebooksMap || {};
    const worldinfoNamesMap = options.worldinfoNamesMap || {};
    const characterLorebookWorldConditions = options.characterLorebookWorldConditions || {};

    // 1. Search Filtering in Modal
    if (modalEl) {
      const searchInput = modalEl.querySelector(".search-input");
      const grid = modalEl.querySelector(".card-grid");
      if (searchInput && grid) {
        searchInput.addEventListener("input", () => {
          const query = searchInput.value.trim().toLowerCase();
          grid.querySelectorAll(".lorebook-picker-card").forEach((card) => {
            const name = (card.getAttribute("data-lorebook-name") || "").toLowerCase();
            const desc = (card.getAttribute("data-lorebook-desc") || "").toLowerCase();
            const tags = (card.getAttribute("data-lorebook-tags") || "").toLowerCase();
            const matches = !query || name.includes(query) || desc.includes(query) || tags.includes(query);
            card.style.display = matches ? "" : "none";
          });
        });
      }

      // 2. Card click in Modal (Add lorebook)
      modalEl.addEventListener("click", async (e) => {
        const card = e.target.closest(".lorebook-picker-card");
        if (!card || card.classList.contains("already-added")) return;

        const lbId = parseInt(card.getAttribute("data-lorebook-id"), 10);
        if (!lbId) return;

        const lb = {
          id: lbId,
          name: card.getAttribute("data-lorebook-fullname") || "",
          description: card.getAttribute("data-lorebook-desc") || "",
          tags: (card.getAttribute("data-lorebook-tags") || "").split(",").filter(Boolean),
          entry_count: parseInt(card.getAttribute("data-lorebook-entries") || "0", 10),
          source: "Benutzerdefiniert",
        };

        if (isNewChat) {
          // Add custom row
          const customList = root.querySelector("#custom-lorebooks-list");
          if (customList) {
            customList.insertAdjacentHTML("beforeend", createLorebookRowHtml(lb, "custom"));
            sortListAlphabetically(customList);
          }

          // Add hidden input
          if (hiddenInputsWrap) {
            const inp = document.createElement("input");
            inp.type = "hidden";
            inp.name = "custom_lorebook_ids";
            inp.value = String(lbId);
            inp.setAttribute("data-custom-id", String(lbId));
            hiddenInputsWrap.appendChild(inp);
          }

          // Mark card as added
          card.classList.add("already-added");
          const statusSpan = card.querySelector(".lorebook-picker-action-label");
          if (statusSpan) {
            statusSpan.textContent = "✓ Bereits aktiv";
            statusSpan.style.color = "var(--text-muted)";
          }

          updateEmptyNotices(root);
          updateCountBadge(root, countBadgeSelector);

          // Close modal
          if (window.AimoModals && typeof window.AimoModals.close === "function") {
            window.AimoModals.close(modalId);
          } else {
            modalEl.classList.remove("open");
          }
        } else if (sessionId) {
          try {
            const res = await fetch(`/api/chat/${sessionId}/lorebooks/custom`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ lorebook_id: lbId }),
            });
            if (!res.ok) {
              const errData = await res.json().catch(() => ({}));
              alert(errData.error || "Fehler beim Hinzufügen des Lorebooks.");
              return;
            }
            const data = await res.json();
            const customList = root.querySelector("#custom-lorebooks-list");
            if (customList) {
              customList.insertAdjacentHTML("beforeend", createLorebookRowHtml(data.lorebook || lb, "custom"));
              sortListAlphabetically(customList);
            }

            card.classList.add("already-added");
            const statusSpan = card.querySelector(".lorebook-picker-action-label");
            if (statusSpan) {
              statusSpan.textContent = "✓ Bereits aktiv";
              statusSpan.style.color = "var(--text-muted)";
            }

            updateEmptyNotices(root);
            updateCountBadge(root, countBadgeSelector);

            if (window.AimoModals && typeof window.AimoModals.close === "function") {
              window.AimoModals.close(modalId);
            } else {
              modalEl.classList.remove("open");
            }
          } catch (err) {
            alert("Netzwerkfehler beim Hinzufügen des Lorebooks.");
          }
        }
      });
    }

    // 3. Delegate Toggle Switch Changes
    root.addEventListener("change", async (e) => {
      const toggle = e.target.closest(".lorebook-toggle-input");
      if (!toggle) return;

      const lbId = parseInt(toggle.getAttribute("data-lorebook-id"), 10);
      const active = toggle.checked;
      if (!lbId) return;

      if (isNewChat) {
        if (hiddenInputsWrap) {
          const existingDisabled = hiddenInputsWrap.querySelector(`input[name="disabled_lorebook_ids"][value="${lbId}"]`);
          if (!active) {
            if (!existingDisabled) {
              const inp = document.createElement("input");
              inp.type = "hidden";
              inp.name = "disabled_lorebook_ids";
              inp.value = String(lbId);
              hiddenInputsWrap.appendChild(inp);
            }
          } else {
            if (existingDisabled) {
              existingDisabled.remove();
            }
          }
        }
        updateCountBadge(root, countBadgeSelector);
      } else if (sessionId) {
        try {
          const res = await fetch(`/api/chat/${sessionId}/lorebooks/toggle`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lorebook_id: lbId, active: active }),
          });
          if (!res.ok) {
            toggle.checked = !active;
            const errData = await res.json().catch(() => ({}));
            alert(errData.error || "Fehler beim Umschalten des Lorebooks.");
            return;
          }
          updateCountBadge(root, countBadgeSelector);
        } catch (err) {
          toggle.checked = !active;
          alert("Netzwerkfehler beim Umschalten des Lorebooks.");
        }
      }
    });

    // 4. Delegate Delete Custom Lorebook Click
    root.addEventListener("click", async (e) => {
      const btn = e.target.closest(".remove-custom-lorebook-btn");
      if (!btn) return;

      const lbId = parseInt(btn.getAttribute("data-lorebook-id"), 10);
      const row = btn.closest(".lorebook-list-item");
      if (!lbId || !row) return;

      if (isNewChat) {
        row.remove();
        if (hiddenInputsWrap) {
          hiddenInputsWrap.querySelectorAll(`input[data-custom-id="${lbId}"]`).forEach((i) => i.remove());
          hiddenInputsWrap.querySelectorAll(`input[data-disabled-id="${lbId}"]`).forEach((i) => i.remove());
        }

        // Reset in picker modal
        if (modalEl) {
          const card = modalEl.querySelector(`.lorebook-picker-card[data-lorebook-id="${lbId}"]`);
          if (card) {
            card.classList.remove("already-added");
            const statusSpan = card.querySelector(".lorebook-picker-action-label");
            if (statusSpan) {
              statusSpan.textContent = "+ Hinzufügen";
              statusSpan.style.color = "var(--gold-accent)";
            }
          }
        }

        updateEmptyNotices(root);
        updateCountBadge(root, countBadgeSelector);
      } else if (sessionId) {
        try {
          const res = await fetch(`/api/chat/${sessionId}/lorebooks/custom/${lbId}`, {
            method: "DELETE",
          });
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            alert(errData.error || "Fehler beim Entfernen des Lorebooks.");
            return;
          }
          row.remove();

          if (modalEl) {
            const card = modalEl.querySelector(`.lorebook-picker-card[data-lorebook-id="${lbId}"]`);
            if (card) {
              card.classList.remove("already-added");
              const statusSpan = card.querySelector(".lorebook-picker-action-label");
              if (statusSpan) {
                statusSpan.textContent = "+ Hinzufügen";
                statusSpan.style.color = "var(--gold-accent)";
              }
            }
          }

          updateEmptyNotices(root);
          updateCountBadge(root, countBadgeSelector);
        } catch (err) {
          alert("Netzwerkfehler beim Entfernen des Lorebooks.");
        }
      }
    });

    // 5. In New Chat: Live Sync with WorldInfo Dropdown
    if (isNewChat && worldinfoSelect) {
      let currentWorldLorebookId = null;

      // Find initial world lorebook if already present
      const initialWiRow = root.querySelector("#default-lorebooks-list .lorebook-list-item[data-source='Welt'], #default-lorebooks-list .lorebook-list-item[data-source='Charakter & Welt']");
      if (initialWiRow) {
        currentWorldLorebookId = parseInt(initialWiRow.getAttribute("data-lorebook-id"), 10);
      }

      worldinfoSelect.addEventListener("change", () => {
        const selectedWiVal = worldinfoSelect.value;
        const selectedWiId = selectedWiVal ? parseInt(selectedWiVal, 10) : null;
        const newWiLb = worldinfoLorebooksMap[selectedWiVal] || null;
        const defContainer = root.querySelector("#default-lorebooks-list");
        if (!defContainer) return;

        // Clean up previous world lorebook
        if (currentWorldLorebookId) {
          const prevRow = defContainer.querySelector(`.lorebook-list-item[data-lorebook-id="${currentWorldLorebookId}"]`);
          if (prevRow) {
            const src = prevRow.getAttribute("data-source");
            if (src === "Charakter & Welt") {
              prevRow.setAttribute("data-source", "Charakter");
              const badge = prevRow.querySelector(".aimo-card-badge");
              if (badge) badge.textContent = "Charakter";
            } else {
              prevRow.remove();
              // Reset in picker modal if not otherwise added
              if (modalEl) {
                const card = modalEl.querySelector(`.lorebook-picker-card[data-lorebook-id="${currentWorldLorebookId}"]`);
                if (card) {
                  card.classList.remove("already-added");
                  const statusSpan = card.querySelector(".lorebook-picker-action-label");
                  if (statusSpan) {
                    statusSpan.textContent = "+ Hinzufügen";
                    statusSpan.style.color = "var(--gold-accent)";
                  }
                }
              }
            }
          }
          currentWorldLorebookId = null;
        }

        // Insert new world lorebook if exists
        if (newWiLb && newWiLb.id) {
          currentWorldLorebookId = newWiLb.id;
          const existingRow = defContainer.querySelector(`.lorebook-list-item[data-lorebook-id="${newWiLb.id}"]`);
          if (existingRow) {
            existingRow.setAttribute("data-source", "Charakter & Welt");
            const badge = existingRow.querySelector(".aimo-card-badge");
            if (badge) badge.textContent = "Charakter & Welt";
          } else {
            defContainer.insertAdjacentHTML("beforeend", createLorebookRowHtml(newWiLb, "default"));
            sortListAlphabetically(defContainer);

            // Mark in modal
            if (modalEl) {
              const card = modalEl.querySelector(`.lorebook-picker-card[data-lorebook-id="${newWiLb.id}"]`);
              if (card) {
                card.classList.add("already-added");
                const statusSpan = card.querySelector(".lorebook-picker-action-label");
                if (statusSpan) {
                  statusSpan.textContent = "✓ Bereits aktiv";
                  statusSpan.style.color = "var(--text-muted)";
                }
              }
            }
          }
        }

        // Synchronize condition-locked character lorebooks
        defContainer.querySelectorAll(".lorebook-list-item").forEach((row) => {
          const lbId = parseInt(row.getAttribute("data-lorebook-id"), 10);
          if (lbId && characterLorebookWorldConditions[lbId]) {
            const reqWiId = parseInt(characterLorebookWorldConditions[lbId], 10);
            const reqWiName = worldinfoNamesMap[reqWiId] || `Welt #${reqWiId}`;
            const actionsOverlay = row.querySelector(".lorebook-item-actions-overlay");
            if (!actionsOverlay) return;

            if (selectedWiId === reqWiId) {
              // Condition met! Unlock and enable
              actionsOverlay.innerHTML = `
                <label class="aimo-switch" title="Lorebook deaktivieren/aktivieren">
                  <input type="checkbox" class="lorebook-toggle-input" data-lorebook-id="${lbId}" checked>
                  <span class="aimo-switch-slider"></span>
                </label>
              `;
              if (hiddenInputsWrap) {
                const hiddenDis = hiddenInputsWrap.querySelector(`input[name="disabled_lorebook_ids"][value="${lbId}"]`);
                if (hiddenDis) hiddenDis.remove();
              }
            } else {
              // Condition not met! Lock and disable
              actionsOverlay.innerHTML = `
                <span class="aimo-card-badge danger lorebook-condition-badge" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;" title="Dieses Lorebook erfordert die Welt '${reqWiName}' und kann in dieser Welt nicht aktiviert werden.">
                  🔒 Inaktiv — Benötigt Welt: ${reqWiName}
                </span>
                <label class="aimo-switch disabled" title="Gesperrt: Passende Welt '${reqWiName}' ist nicht aktiv.">
                  <input type="checkbox" class="lorebook-toggle-input" data-lorebook-id="${lbId}" data-required-worldinfo-id="${reqWiId}" disabled>
                  <span class="aimo-switch-slider"></span>
                </label>
              `;
              if (hiddenInputsWrap) {
                let hiddenDis = hiddenInputsWrap.querySelector(`input[name="disabled_lorebook_ids"][value="${lbId}"]`);
                if (!hiddenDis) {
                  hiddenDis = document.createElement("input");
                  hiddenDis.type = "hidden";
                  hiddenDis.name = "disabled_lorebook_ids";
                  hiddenDis.value = String(lbId);
                  hiddenInputsWrap.appendChild(hiddenDis);
                }
              }
            }
          }
        });

        updateEmptyNotices(root);
        updateCountBadge(root, countBadgeSelector);
      });
    }

    // Initial count update
    updateCountBadge(root, countBadgeSelector);
    updateEmptyNotices(root);
  }

  window.initLorebookManager = initLorebookManager;
})();
