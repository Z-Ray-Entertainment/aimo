// Clickable Table Rows & Instant Live Search for My Creations
if (!window.AIMO_CREATIONS_TABLE_LOADED) {
  window.AIMO_CREATIONS_TABLE_LOADED = true;
  document.addEventListener("DOMContentLoaded", () => {
  // Clickable table rows (e.g. in My Creations)
  document.addEventListener("click", (e) => {
    const row = e.target.closest(".aimo-clickable-row");
    if (!row) return;
    // If clicked directly on an interactive element, let its native action run
    if (e.target.closest("a, button, input, select, label, textarea")) return;
    const href = row.getAttribute("data-href");
    if (href) {
      window.location.href = href;
    }
  });

  // Client-side instant live search for creations table
  const creationsSearchInput = document.getElementById("creations-search-input");
  const creationsTableBody = document.getElementById("creations-table-body");
  if (creationsSearchInput && creationsTableBody) {
    creationsSearchInput.addEventListener("input", (e) => {
      const term = e.target.value.trim().toLowerCase();
      const rows = creationsTableBody.querySelectorAll(".aimo-clickable-row");
      rows.forEach((row) => {
        const text = row.textContent.toLowerCase();
        if (!term || text.includes(term)) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      });
    });
  }
  });
}
