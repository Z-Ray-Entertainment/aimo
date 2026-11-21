from __future__ import annotations

from enum import StrEnum
from typing import Any


class EnumString(str):
    """String subclass exposing `.value` for templates expecting domain Enum values."""

    @property
    def value(self) -> str:
        return str(self)


_ENUM_FIELDS = {"gender", "role", "emotion"}


class AttrDict(dict):
    """Dictionary supporting attribute access for Jinja2 templates and Flask views."""

    def __getattr__(self, key: str) -> Any:
        try:
            val = self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc
        if isinstance(val, dict) and not isinstance(val, AttrDict):
            return AttrDict(val)
        if isinstance(val, list):
            return [AttrDict(x) if isinstance(x, dict) and not isinstance(x, AttrDict) else x for x in val]
        return val

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def wrap_dto(obj: Any) -> Any:
    if isinstance(obj, dict) and not isinstance(obj, AttrDict):
        wrapped: dict[str, Any] = {}
        for k, v in obj.items():
            if k in _ENUM_FIELDS and isinstance(v, str):
                wrapped[k] = EnumString(v)
            else:
                wrapped[k] = wrap_dto(v)
        return AttrDict(wrapped)
    if isinstance(obj, list):
        return [wrap_dto(item) for item in obj]
    return obj


class FunctionPermission(StrEnum):
    ADMIN_ACCESS = "admin_access"
    CHARACTER_CREATE = "character_create"
    CHARACTER_EDIT = "character_edit"
    CHARACTER_DELETE = "character_delete"
    LOREBOOK_CREATE = "lorebook_create"
    LOREBOOK_EDIT = "lorebook_edit"
    LOREBOOK_DELETE = "lorebook_delete"
    WORLDINFO_CREATE = "worldinfo_create"
    WORLDINFO_EDIT = "worldinfo_edit"
    WORLDINFO_DELETE = "worldinfo_delete"
    CHAT_ACCESS = "chat_access"
    PERSONA_MANAGE = "persona_manage"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non-binary"


class Emotion(StrEnum):
    ADMIRE = "admire"
    AMUSED = "amused"
    ANGER = "anger"
    ANNOYED = "annoyed"
    APPROVAL = "approval"
    CARING = "caring"
    CONFUSED = "confused"
    CURIOUS = "curious"
    DESIRE = "desire"
    DISAPPOINTED = "disappointed"
    DISAPPROVAL = "disapproval"
    DISGUST = "disgust"
    EMBARRASSED = "embarrassed"
    EXCITED = "excited"
    FEAR = "fear"
    GRATITUDE = "gratitude"
    GRIEF = "grief"
    JOY = "joy"
    LOVE = "love"
    NERVOUSNESS = "nervousness"
    NEUTRAL = "neutral"
    OPTIMISTIC = "optimistic"
    PRIDE = "pride"
    REALIZE = "realize"
    RELIEF = "relief"
    REMORSE = "remorse"
    SAD = "sad"
    SURPRISE = "surprise"


LANGUAGE_METADATA: dict[str, dict[str, str]] = {
    "en": {"flag": "🇬🇧", "label": "English"},
    "zh": {"flag": "🇨🇳", "label": "中文"},
    "hi": {"flag": "🇮🇳", "label": "हिन्दी"},
    "es": {"flag": "🇪🇸", "label": "Español"},
    "fr": {"flag": "🇫🇷", "label": "Français"},
    "ar": {"flag": "🇸🇦", "label": "العربية"},
    "bn": {"flag": "🇧🇩", "label": "বাংলা"},
    "pt": {"flag": "🇵🇹", "label": "Português"},
    "ru": {"flag": "🇷🇺", "label": "Русский"},
    "ur": {"flag": "🇵🇰", "label": "اردو"},
    "id": {"flag": "🇮🇩", "label": "Bahasa Indonesia"},
    "de": {"flag": "🇩🇪", "label": "Deutsch"},
    "ja": {"flag": "🇯🇵", "label": "日本語"},
    "tr": {"flag": "🇹🇷", "label": "Türkçe"},
    "ko": {"flag": "🇰🇷", "label": "한국어"},
    "vi": {"flag": "🇻🇳", "label": "Tiếng Việt"},
    "it": {"flag": "🇮🇹", "label": "Italiano"},
    "pl": {"flag": "🇵🇱", "label": "Polski"},
    "nl": {"flag": "🇳🇱", "label": "Nederlands"},
    "th": {"flag": "🇹🇭", "label": "ไทย"},
}
