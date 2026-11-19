from __future__ import annotations

import gettext
from pathlib import Path
from threading import Lock

FLASK_LOCALES_DIR = Path(__file__).resolve().parent / "locales"
RTL_LANGUAGES: frozenset[str] = frozenset({"ar", "ur"})
_TRANSLATOR_CACHE: dict[str, tuple[float, gettext.NullTranslations]] = {}
_CACHE_LOCK = Lock()


def normalize_language(raw: str | None, default: str = "en") -> str:
    if not isinstance(raw, str):
        return default
    cleaned = raw.strip().lower()[:2]
    return cleaned if cleaned else default


def get_text_direction(language: str | None = "en") -> str:
    return "rtl" if normalize_language(language) in RTL_LANGUAGES else "ltr"


def get_translator(language: str | None = "en") -> gettext.NullTranslations:
    lang = normalize_language(language, default="en")
    mo_path = FLASK_LOCALES_DIR / lang / "LC_MESSAGES" / "messages.mo"
    mtime = mo_path.stat().st_mtime if mo_path.is_file() else 0.0
    with _CACHE_LOCK:
        cached = _TRANSLATOR_CACHE.get(lang)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        translator = gettext.translation(
            "messages",
            localedir=str(FLASK_LOCALES_DIR),
            languages=[lang],
            fallback=True,
        )
        _TRANSLATOR_CACHE[lang] = (mtime, translator)
        return translator


def t(msgid: str, language: str | None = "en") -> str:
    if not msgid:
        return msgid
    lang = normalize_language(language, default="en")
    if lang == "en":
        return msgid
    return get_translator(lang).gettext(msgid)


def gettext_noop(msgid: str) -> str:
    return msgid


def ensure_compiled_locales() -> int:
    from shared.i18n import ensure_compiled_locales as _ensure_compiled_locales

    compiled = _ensure_compiled_locales(FLASK_LOCALES_DIR)
    if compiled:
        with _CACHE_LOCK:
            _TRANSLATOR_CACHE.clear()
    return compiled


JS_I18N_KEYS: tuple[str, ...] = (
    gettext_noop("Error adding lorebook."),
    gettext_noop("Network error while adding lorebook."),
    gettext_noop("Error toggling lorebook."),
    gettext_noop("Network error while toggling lorebook."),
    gettext_noop("Error removing lorebook."),
    gettext_noop("Network error while removing lorebook."),
    gettext_noop("Reset this prompt in all languages back to the built-in default?"),
    gettext_noop("Please select a portrait image first."),
    gettext_noop("Image analysis error: {error}"),
    gettext_noop("Please enter at least one trigger or response."),
    gettext_noop("Please enter a meaningful character description in the 'Basic Info' tab first."),
    gettext_noop("Please enter a title or prose text first so the assistant can derive relevant tags."),
    gettext_noop("Error deriving tags: {error}"),
    gettext_noop("Connection error: {error}"),
    gettext_noop("Timeout while sending."),
    gettext_noop("Timeout"),
    gettext_noop("Connection to backend (aimo-core) lost."),
    gettext_noop("Backend connection error"),
    gettext_noop("Connection to AI backend lost."),
    gettext_noop("AI connection error"),
    gettext_noop("Error sending message."),
    gettext_noop("Error"),
    gettext_noop("Connection to backend lost: {error}"),
    gettext_noop("Timeout: {error}"),
    gettext_noop("Ollama connection error: {error}"),
    gettext_noop("Connection to Ollama (or LLMProvider) lost."),
    gettext_noop("Ollama connection error"),
    gettext_noop("Timeout while regenerating."),
    gettext_noop("Error while regenerating."),
    gettext_noop("Ollama error"),
    gettext_noop("Success"),
    gettext_noop("Warning"),
    gettext_noop("Notice"),
    gettext_noop("Close"),
    gettext_noop("Crops active"),
    gettext_noop("1:1 Cover active"),
    gettext_noop("Analyzing image"),
    gettext_noop("✨ Analyzing portrait and extracting appearance"),
    gettext_noop("Drafting dialogue"),
    gettext_noop("✨ Analyzing character description"),
    gettext_noop("✨ Formulating response"),
    gettext_noop("⏳ Analyzing image (Save & Close locked)"),
    gettext_noop("Not translated yet (click to enter manually or AI translate)"),
    gettext_noop("Translation may be outdated (click to review)"),
    gettext_noop("Appearance extracted from image successfully."),
    gettext_noop("No appearance extracted."),
    gettext_noop("Server error ({status}): Could not extract appearance."),
    gettext_noop("Please select a portrait image first to extract image features."),
    gettext_noop("Image features extracted"),
    gettext_noop("Image analysis failed."),
    gettext_noop("Image analysis error"),
    gettext_noop("Connection error during image analysis."),
    gettext_noop("Connection error"),
    gettext_noop("Create New Persona"),
    gettext_noop("Edit Persona"),
    gettext_noop("Used in active chats (deletion protection)"),
    gettext_noop("Delete persona"),
    gettext_noop("Deletion locked"),
    gettext_noop("Delete"),
    gettext_noop("Translating..."),
    gettext_noop("Translation paused"),
    gettext_noop("Cloud AI Mode (On-Demand)"),
    gettext_noop("Idle"),
    gettext_noop("No active translation"),
    gettext_noop("Last finished:"),
    gettext_noop("Error:"),
    gettext_noop("Character"),
    gettext_noop("Lorebook"),
    gettext_noop("Lorebook Entry"),
    gettext_noop("World"),
    gettext_noop("Location"),
    gettext_noop("Location Tags"),
    gettext_noop("Event"),
    gettext_noop("Character Event"),
)


def get_js_translations(language: str | None = "en") -> dict[str, str]:
    lang = normalize_language(language, default="en")
    if lang == "en":
        return {k: k for k in JS_I18N_KEYS}
    translator = get_translator(lang)
    return {k: translator.gettext(k) for k in JS_I18N_KEYS}
