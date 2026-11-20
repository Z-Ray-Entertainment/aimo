import { getCharacterContext } from "./creator_core.js";

export function initSparkleAuthor() {
  const btn = document.getElementById("sparkle-improve-btn");
  const textarea = document.getElementById("char-description-textarea");
  const nameInput = document.getElementById("char-name-input");
  const genderSelect = document.querySelector('select[name="gender"]');
  if (!textarea || !btn) return;

  btn.addEventListener("click", async () => {
    const origBtnHtml = window.setButtonLoading(btn, "Optimiere Beschreibung");

    const origPlaceholder = textarea.placeholder;
    if (!textarea.value.trim()) {
      textarea.placeholder = "✨ Optimiere Beschreibung";
    }

    try {
      const language = textarea.dataset.i18nActiveLang || document.body.dataset.userLanguage || "en";
      const resp = await fetch("/api/characters/sparkle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: nameInput ? nameInput.value : "",
          gender: genderSelect ? genderSelect.value : "",
          description: textarea.value,
          language,
        }),
      });

      let data = null;
      try {
        data = await resp.json();
      } catch (_) {
        data = null;
      }

      if (resp.ok && data && data.description) {
        textarea.value = data.description;
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
        if (window.showToastSuccess) {
          window.showToastSuccess("Beschreibung erfolgreich generiert.");
        }
      } else {
        const errMsg = (data && data.error)
          || (resp.ok ? "Keine Beschreibung erhalten." : `Serverfehler (${resp.status}): Konnte Beschreibung nicht generieren.`);
        if (window.showToastError) window.showToastError(errMsg); else alert(errMsg);
      }
    } catch (err) {
      const errText = "Verbindungsfehler zum KI-Autor: " + (err.message || err);
      if (window.showToastError) window.showToastError(errText); else alert(errText);
    } finally {
      window.resetButtonLoading(btn, '<span class="icon-mono">✨</span><span>KI-Autor Optimierung</span>');
      textarea.placeholder = origPlaceholder;
    }
  });
}

export function initVisionAppearance() {
  const btn = document.getElementById("extract-appearance-btn");
  const textarea = document.getElementById("char-appearance-textarea");
  const fileInput = document.getElementById("primary-portrait-input");
  if (!btn || !textarea) return;

  btn.addEventListener("click", async () => {
    const ctx = getCharacterContext();
    const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
    if (!hasFile && !ctx.characterId) {
      if (window.showToastWarning) {
        window.showToastWarning("Bitte wähle zuerst ein Porträtbild aus.");
      } else {
        alert(window.t("Please select a portrait image first."));
      }
      return;
    }

    const origPlaceholder = textarea.placeholder;
    const origBtnHtml = window.setButtonLoading(btn, window.t("Analyzing image"));

    if (!textarea.value.trim()) {
      textarea.placeholder = window.t("✨ Analyzing portrait and extracting appearance");
    }

    try {
      let resp;
      if (hasFile) {
        const fd = new FormData();
        fd.append("primary_portrait", fileInput.files[0]);
        resp = await fetch("/api/characters/extract-appearance", {
          method: "POST",
          body: fd,
        });
      } else {
        resp = await fetch("/api/characters/extract-appearance", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ character_id: ctx.characterId }),
        });
      }

      let data = null;
      try {
        data = await resp.json();
      } catch (_) {
        data = null;
      }

      if (resp.ok && data && data.appearance) {
        textarea.value = data.appearance;
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
        if (window.showToastSuccess) {
          window.showToastSuccess(window.t("Appearance extracted from image successfully."));
        }
      } else {
        const errMsg = (data && data.error)
          || (resp.ok
            ? window.t("No appearance extracted.")
            : window.t("Server error ({status}): Could not extract appearance.", { status: resp.status }));
        if (window.showToastError) window.showToastError(errMsg); else alert(errMsg);
      }
    } catch (err) {
      const errMsg = window.t("Image analysis error: {error}", { error: err });
      if (window.showToastError) {
        window.showToastError(errMsg);
      } else {
        alert(errMsg);
      }
    } finally {
      window.resetButtonLoading(btn, origBtnHtml);
      textarea.placeholder = origPlaceholder;
    }
  });
}

