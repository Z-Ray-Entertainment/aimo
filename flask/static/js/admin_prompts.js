document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".btn-reset-prompt").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetName = btn.dataset.target;
      if (!targetName) return;

      if (!confirm("Möchtest du diesen Prompt wirklich auf den Standardwert zurücksetzen?")) {
        return;
      }

      const textarea = document.querySelector(`textarea[name="${targetName}"]`);
      if (!textarea) return;

      textarea.value = textarea.dataset.defaultPrompt || "";
      textarea.dispatchEvent(new Event("input", { bubbles: true }));

      if (window.showToastSuccess) {
        window.showToastSuccess("Standard-Prompt eingesetzt. Klicke auf 'Prompts speichern', um die Änderung zu übernehmen.");
      }
    });
  });
});
