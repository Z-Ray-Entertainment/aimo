export function initWorldLocationsFilter() {
  const worldSelect = document.getElementById("char-worldinfo-select");
  const container = document.getElementById("worldinfo-locations-container");
  const initialSelect = document.getElementById("char-initial-location-select");
  const preferredSelect = document.getElementById("char-preferred-locations-select");
  const dislikedSelect = document.getElementById("char-disliked-locations-select");

  if (!worldSelect || !container) return;

  // Cache template options once from DOM
  const initialMasterOptions = initialSelect
    ? Array.from(initialSelect.querySelectorAll("option[data-worldinfo-id]"))
    : [];
  const preferredMasterOptions = preferredSelect
    ? Array.from(preferredSelect.querySelectorAll("option[data-worldinfo-id]"))
    : [];
  const dislikedMasterOptions = dislikedSelect
    ? Array.from(dislikedSelect.querySelectorAll("option[data-worldinfo-id]"))
    : [];

  function updateLocationsForWorld(worldId, preserveSelected = true) {
    if (!worldId) {
      container.style.display = "none";
      if (initialSelect) initialSelect.value = "";
      if (preferredSelect) Array.from(preferredSelect.options).forEach(o => { o.selected = false; });
      if (dislikedSelect) Array.from(dislikedSelect.options).forEach(o => { o.selected = false; });
      return;
    }

    container.style.display = "flex";

    const prevInitial = preserveSelected && initialSelect ? initialSelect.value : "";
    const prevPreferred = preserveSelected && preferredSelect
      ? Array.from(preferredSelect.selectedOptions).map(o => o.value)
      : [];
    const prevDisliked = preserveSelected && dislikedSelect
      ? Array.from(dislikedSelect.selectedOptions).map(o => o.value)
      : [];

    if (initialSelect) {
      initialSelect.innerHTML = '<option value="">-- Kein fester Startort --</option>';
      initialMasterOptions
        .filter(opt => opt.dataset.worldinfoId === String(worldId))
        .forEach(opt => {
          const clone = opt.cloneNode(true);
          if (String(clone.value) === String(prevInitial)) clone.selected = true;
          initialSelect.appendChild(clone);
        });
    }

    if (preferredSelect) {
      preferredSelect.innerHTML = "";
      preferredMasterOptions
        .filter(opt => opt.dataset.worldinfoId === String(worldId))
        .forEach(opt => {
          const clone = opt.cloneNode(true);
          if (prevPreferred.includes(String(clone.value))) clone.selected = true;
          preferredSelect.appendChild(clone);
        });
    }

    if (dislikedSelect) {
      dislikedSelect.innerHTML = "";
      dislikedMasterOptions
        .filter(opt => opt.dataset.worldinfoId === String(worldId))
        .forEach(opt => {
          const clone = opt.cloneNode(true);
          if (prevDisliked.includes(String(clone.value))) clone.selected = true;
          dislikedSelect.appendChild(clone);
        });
    }
  }

  worldSelect.addEventListener("change", () => {
    updateLocationsForWorld(worldSelect.value, false);
  });

  if (worldSelect.value) {
    updateLocationsForWorld(worldSelect.value, true);
  }
}


export function initLorebooksManager() {
  const filterInput = document.getElementById("lorebook-filter-input");
  const pickerList = document.getElementById("lorebook-picker-list");
  const linkedList = document.getElementById("linked-lorebooks-list");
  const emptyNotice = document.getElementById("lorebook-empty-notice");

  if (!pickerList || !linkedList) return;

  function updateEmptyNotice() {
    if (emptyNotice) {
      const count = linkedList.querySelectorAll(".lorebook-list-item").length;
      emptyNotice.style.display = count === 0 ? "block" : "none";
    }
  }

  function getAvailableWorldinfos() {
    const worldSelect = document.getElementById("char-worldinfo-select");
    if (!worldSelect) return [];
    return Array.from(worldSelect.querySelectorAll("option"))
      .filter(opt => opt.value)
      .map(opt => ({ id: opt.value, name: opt.textContent.trim() }));
  }

  filterInput?.addEventListener("input", () => {
    const query = filterInput.value.toLowerCase().trim();
    pickerList.querySelectorAll(".lorebook-picker-item").forEach(item => {
      const name = (item.getAttribute("data-name") || "").toLowerCase();
      const desc = (item.getAttribute("data-desc") || "").toLowerCase();
      item.style.display = (name.includes(query) || desc.includes(query)) ? "flex" : "none";
    });
  });

  pickerList.querySelectorAll(".lorebook-picker-item").forEach(item => {
    item.addEventListener("click", () => {
      if (item.classList.contains("already-added")) return;

      const lbId = item.getAttribute("data-id");
      const lbName = item.getAttribute("data-fullname");
      const lbDesc = item.getAttribute("data-desc");

      const row = document.createElement("div");
      row.className = "lorebook-list-item";
      row.setAttribute("data-lorebook-id", lbId);
      row.style.display = "flex";
      row.style.justifyContent = "space-between";
      row.style.alignItems = "center";
      row.style.gap = "1rem";
      row.style.flexWrap = "wrap";

      const hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = "linked_lorebook_ids";
      hidden.value = lbId;
      row.appendChild(hidden);

      const info = document.createElement("div");
      info.style.flex = "1";
      info.style.minWidth = "200px";
      info.innerHTML = `<div style="font-weight: 700; color: var(--gold-accent); font-size: 0.95rem;">${lbName}</div>`
        + (lbDesc ? `<div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.15rem;">${lbDesc}</div>` : "");
      row.appendChild(info);

      const actionsDiv = document.createElement("div");
      actionsDiv.style.display = "flex";
      actionsDiv.style.alignItems = "center";
      actionsDiv.style.gap = "0.65rem";

      let optionsHtml = '<option value="">🌍 Alle Welten (Immer aktiv)</option>';
      getAvailableWorldinfos().forEach(wi => {
        optionsHtml += `<option value="${wi.id}">🌐 Nur in Welt: ${wi.name}</option>`;
      });

      const select = document.createElement("select");
      select.name = `lorebook_world_condition_${lbId}`;
      select.style.fontSize = "0.82rem";
      select.style.padding = "0.35rem 0.6rem";
      select.style.maxWidth = "240px";
      select.title = "Wann soll dieses Lorebook aktiv sein?";
      select.innerHTML = optionsHtml;
      actionsDiv.appendChild(select);

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "aimo-btn danger remove-lorebook-btn";
      delBtn.title = "Lorebook entkoppeln";
      delBtn.innerHTML = '<span class="icon-mono">🗑️</span>';
      delBtn.addEventListener("click", () => {
        row.remove();
        item.classList.remove("already-added");
        const badge = item.querySelector(".picker-status-badge");
        if (badge) badge.textContent = "+ Hinzufügen";
        updateEmptyNotice();
      });
      actionsDiv.appendChild(delBtn);

      row.appendChild(actionsDiv);
      linkedList.appendChild(row);

      item.classList.add("already-added");
      const statusBadge = item.querySelector(".picker-status-badge");
      if (statusBadge) statusBadge.textContent = "✓ Verknüpft";
      updateEmptyNotice();

      if (window.AimoModals && typeof window.AimoModals.close === "function") {
        window.AimoModals.close("add-lorebook-modal");
      } else {
        document.getElementById("add-lorebook-modal")?.classList.remove("open");
      }
    });
  });

  linkedList.querySelectorAll(".remove-lorebook-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const row = btn.closest(".lorebook-list-item");
      const lbId = btn.getAttribute("data-id");
      if (row) row.remove();
      if (lbId) {
        const pickerItem = pickerList.querySelector(`.lorebook-picker-item[data-id="${lbId}"]`);
        if (pickerItem) {
          pickerItem.classList.remove("already-added");
          const badge = pickerItem.querySelector(".picker-status-badge");
          if (badge) badge.textContent = "+ Hinzufügen";
        }
      }
      updateEmptyNotice();
    });
  });
}

