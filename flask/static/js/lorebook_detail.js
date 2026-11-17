document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".suggest-tags-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const tagsInput = document.getElementById(btn.getAttribute("data-tags-id"));
      const titleInput = document.getElementById(btn.getAttribute("data-title-id"));
      const contentInput = document.getElementById(btn.getAttribute("data-content-id"));

      const title = titleInput ? titleInput.value.trim() : "";
      const content = contentInput ? contentInput.value.trim() : "";

      if (!title && !content) {
        if (window.showToastWarning) {
          window.showToastWarning("Bitte trage zuerst einen Titel oder Fließtext ein, damit der Assistent relevante Tags ableiten kann.");
        } else {
          alert("Bitte trage zuerst einen Titel oder Fließtext ein, damit der Assistent relevante Tags ableiten kann.");
        }
        return;
      }

      const origHtml = window.setButtonLoading(btn, "Ermittle Tags");

      try {
        const resp = await fetch("/api/lorebooks/suggest-tags", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title, content }),
        });
        const data = await resp.json();
        if (resp.ok && data.tags_string) {
          if (tagsInput) {
            const current = tagsInput.value.trim();
            if (current) {
              const existing = current.split(",").map(t => t.trim().toLowerCase()).filter(Boolean);
              const combined = Array.from(new Set([...existing, ...data.tags]));
              tagsInput.value = combined.join(", ");
            } else {
              tagsInput.value = data.tags_string;
            }
          }
          if (window.showToastSuccess) {
            window.showToastSuccess("Relevante Tags erfolgreich ermittelt.");
          }
        } else if (data.error) {
          if (window.showToastError) {
            window.showToastError(`Fehler bei der Tag-Ermittlung: ${data.error}`);
          } else {
            alert(`Fehler bei der Tag-Ermittlung: ${data.error}`);
          }
        }
      } catch (err) {
        if (window.showToastError) {
          window.showToastError(`Verbindungsfehler: ${err.message}`);
        } else {
          alert(`Verbindungsfehler: ${err.message}`);
        }
      } finally {
        window.resetButtonLoading(btn, origHtml);
      }
    });
  });
});
