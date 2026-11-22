import { initSparkleAuthor, initVisionAppearance } from "./creator_ai.js";
import { initWorldLocationsFilter, initLorebooksManager } from "./creator_world.js";
import { initDialogueManager, initCropper, initImageViewer } from "./creator_media.js";

export function getFormElement() {
  return document.getElementById("character-main-form");
}

export function getCharacterContext() {
  const form = getFormElement();
  return {
    characterId: form?.dataset.characterId || null,
    characterName: form?.dataset.characterName || "",
    activePersonaName: form?.dataset.activePersona || "Du",
  };
}

function saveSpriteScrollPos() {
  try {
    sessionStorage.setItem("aimo_sprite_scroll_y", String(window.scrollY || window.pageYOffset || 0));
  } catch (_) {}
}

function restoreSpriteScroll() {
  try {
    const savedY = sessionStorage.getItem("aimo_sprite_scroll_y");
    if (savedY !== null) {
      sessionStorage.removeItem("aimo_sprite_scroll_y");
      const targetY = parseInt(savedY, 10);
      if (!Number.isNaN(targetY) && targetY > 0) {
        if ("scrollRestoration" in history) {
          history.scrollRestoration = "manual";
        }
        const restoreScroll = () => window.scrollTo({ top: targetY, behavior: "instant" });
        restoreScroll();
        requestAnimationFrame(restoreScroll);
        window.addEventListener("load", restoreScroll, { once: true });
      }
    }
  } catch (_) {}
}

function initSpriteScrollHandlers() {
  document.addEventListener("submit", (e) => {
    const form = e.target.closest("form[data-save-sprite-scroll]");
    if (form) saveSpriteScrollPos();
  });
}

function init() {
  restoreSpriteScroll();
  initSpriteScrollHandlers();
  initSparkleAuthor();
  initVisionAppearance();
  initWorldLocationsFilter();
  initDialogueManager();
  initLorebooksManager();
  initCropper();
  initImageViewer();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
