export function initWorldLocationsFilter() {
  const worldSelect = document.getElementById("char-worldinfo-select");
  const container = document.getElementById("worldinfo-locations-container");
  const initialWrapper = document.getElementById("char-initial-location-wrapper");
  const initialSelect = document.getElementById("char-initial-location-select");
  const preferredList = document.getElementById("preferred-locations-list");
  const dislikedList = document.getElementById("disliked-locations-list");
  const preferredEmpty = document.getElementById("preferred-locations-empty");
  const dislikedEmpty = document.getElementById("disliked-locations-empty");
  const catalogEl = document.getElementById("world-locations-catalog");

  const modal = document.getElementById("add-world-location-modal");
  const modalTitle = document.getElementById("world-location-modal-title");
  const filterInput = document.getElementById("world-location-filter-input");
  const pickerList = document.getElementById("world-location-picker-list");
  const pickerEmpty = document.getElementById("world-location-picker-empty");

  if (!worldSelect || !container) return;

  let locationsCatalog = [];
  if (catalogEl) {
    try {
      locationsCatalog = JSON.parse(catalogEl.textContent || "[]");
    } catch (_) {
      locationsCatalog = [];
    }
  }

  const initialDefaultOption = initialSelect?.querySelector('option[value=""]')?.outerHTML
    || '<option value="">-- No fixed starting location --</option>';
  const initialMasterOptions = initialSelect
    ? Array.from(initialSelect.querySelectorAll("option[data-worldinfo-id]"))
    : [];

  let activeTarget = "preferred";

  function updateEmptyNotices() {
    if (preferredEmpty && preferredList) {
      preferredEmpty.style.display = preferredList.querySelectorAll(".world-location-item").length === 0 ? "block" : "none";
    }
    if (dislikedEmpty && dislikedList) {
      dislikedEmpty.style.display = dislikedList.querySelectorAll(".world-location-item").length === 0 ? "block" : "none";
    }
  }

  function getAssignedLocationIds() {
    const ids = new Set();
    [preferredList, dislikedList].forEach(list => {
      if (!list) return;
      list.querySelectorAll(".world-location-item[data-location-id]").forEach(item => {
        ids.add(String(item.getAttribute("data-location-id")));
      });
    });
    return ids;
  }

  function createLocationRow(loc, target) {
    const row = document.createElement("div");
    row.className = "world-location-item";
    row.setAttribute("data-location-id", String(loc.id));

    const hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = target === "disliked" ? "disliked_location_ids" : "preferred_location_ids";
    hidden.value = String(loc.id);
    row.appendChild(hidden);

    const nameSpan = document.createElement("span");
    nameSpan.className = "world-location-name";
    nameSpan.textContent = loc.name;
    row.appendChild(nameSpan);

    const removeTitle = modal?.dataset.removeTitle || "Remove location";
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "aimo-btn danger aimo-btn-sm aimo-btn-icon remove-world-location-btn";
    delBtn.title = removeTitle;
    delBtn.setAttribute("aria-label", removeTitle);
    delBtn.innerHTML = '<span class="icon-mono">🗑️</span>';
    row.appendChild(delBtn);

    return row;
  }

  function updatePickerEmptyState() {
    if (!pickerList || !pickerEmpty) return;
    const allItems = Array.from(pickerList.querySelectorAll(".lorebook-picker-item"));
    const visibleItems = allItems.filter(item => item.style.display !== "none");

    if (allItems.length === 0) {
      pickerEmpty.textContent = modal?.dataset.emptyAllAssigned || "All locations of this world are already assigned.";
      pickerEmpty.style.display = "block";
    } else if (visibleItems.length === 0) {
      pickerEmpty.textContent = modal?.dataset.emptySearch || "No matching locations found.";
      pickerEmpty.style.display = "block";
    } else {
      pickerEmpty.style.display = "none";
    }
  }

  function renderPickerForWorld(worldId) {
    if (!pickerList) return;
    const assigned = getAssignedLocationIds();
    const available = locationsCatalog
      .filter(loc => String(loc.worldinfo_id) === String(worldId) && !assigned.has(String(loc.id)))
      .sort((a, b) => a.name.localeCompare(b.name));

    pickerList.innerHTML = "";
    const addLabel = modal?.dataset.addLabel || "+ Add";

    available.forEach(loc => {
      const item = document.createElement("div");
      item.className = "lorebook-picker-item";
      item.setAttribute("data-id", String(loc.id));
      item.setAttribute("data-name", loc.name.toLowerCase());
      item.setAttribute("data-desc", (loc.description || "").toLowerCase());

      const info = document.createElement("div");
      const titleDiv = document.createElement("div");
      titleDiv.style.fontWeight = "700";
      titleDiv.style.color = "var(--gold-accent)";
      titleDiv.textContent = loc.name;
      info.appendChild(titleDiv);

      if (loc.description) {
        const descDiv = document.createElement("div");
        descDiv.className = "world-location-picker-desc";
        descDiv.textContent = loc.description;
        info.appendChild(descDiv);
      }

      const badge = document.createElement("span");
      badge.className = "picker-status-badge";
      badge.style.fontSize = "0.8rem";
      badge.style.color = "var(--text-muted)";
      badge.style.flexShrink = "0";
      badge.textContent = addLabel;

      item.appendChild(info);
      item.appendChild(badge);
      item.addEventListener("click", () => {
        const targetList = activeTarget === "disliked" ? dislikedList : preferredList;
        if (targetList) {
          targetList.appendChild(createLocationRow(loc, activeTarget));
        }
        item.remove();
        updateEmptyNotices();
        updatePickerEmptyState();
      });

      pickerList.appendChild(item);
    });

    updatePickerEmptyState();
  }

  function updateLocationsForWorld(worldId, preserveSelected = true) {
    if (!worldId) {
      container.style.display = "none";
      if (initialWrapper) initialWrapper.style.display = "none";
      if (initialSelect) initialSelect.value = "";
      if (preferredList) preferredList.innerHTML = "";
      if (dislikedList) dislikedList.innerHTML = "";
      updateEmptyNotices();
      return;
    }

    container.style.display = "flex";
    if (initialWrapper) initialWrapper.style.display = "block";

    const prevInitial = preserveSelected && initialSelect ? initialSelect.value : "";
    if (initialSelect) {
      initialSelect.innerHTML = initialDefaultOption;
      initialMasterOptions
        .filter(opt => opt.dataset.worldinfoId === String(worldId))
        .forEach(opt => {
          const clone = opt.cloneNode(true);
          if (String(clone.value) === String(prevInitial)) clone.selected = true;
          initialSelect.appendChild(clone);
        });
    }

    if (!preserveSelected) {
      if (preferredList) preferredList.innerHTML = "";
      if (dislikedList) dislikedList.innerHTML = "";
    }
    updateEmptyNotices();
  }

  document.querySelectorAll(".add-world-location-btn[data-location-target]").forEach(btn => {
    btn.addEventListener("click", () => {
      if (!worldSelect.value) return;
      activeTarget = btn.getAttribute("data-location-target") === "disliked" ? "disliked" : "preferred";

      if (modalTitle && modal) {
        const titleText = activeTarget === "disliked"
          ? (modal.dataset.titleDisliked || "Add Disliked Location")
          : (modal.dataset.titlePreferred || "Add Preferred Location");
        modalTitle.innerHTML = `<span class="icon-mono">📍</span> ${titleText}`;
      }

      if (filterInput) filterInput.value = "";
      renderPickerForWorld(worldSelect.value);

      if (window.AimoModals && typeof window.AimoModals.open === "function") {
        window.AimoModals.open("add-world-location-modal");
      } else {
        modal?.classList.add("open");
      }
      requestAnimationFrame(() => filterInput?.focus());
    });
  });

  filterInput?.addEventListener("input", () => {
    if (!pickerList) return;
    const query = filterInput.value.toLowerCase().trim();
    pickerList.querySelectorAll(".lorebook-picker-item").forEach(item => {
      const name = item.getAttribute("data-name") || "";
      const desc = item.getAttribute("data-desc") || "";
      item.style.display = (name.includes(query) || desc.includes(query)) ? "flex" : "none";
    });
    updatePickerEmptyState();
  });

  [preferredList, dislikedList].forEach(list => {
    list?.addEventListener("click", (e) => {
      const removeBtn = e.target.closest(".remove-world-location-btn");
      if (!removeBtn) return;
      removeBtn.closest(".world-location-item")?.remove();
      updateEmptyNotices();
    });
  });

  worldSelect.addEventListener("change", () => {
    updateLocationsForWorld(worldSelect.value, false);
  });

  updateLocationsForWorld(worldSelect.value, true);
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

