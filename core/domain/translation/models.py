from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import hashlib


class Language(StrEnum):
    EN = "en"
    DE = "de"
    FR = "fr"
    ES = "es"
    IT = "it"
    JA = "ja"

    @classmethod
    def resolve(cls, raw: str | "Language") -> "Language":
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, str):
            return cls.DE
        cleaned = raw.strip().lower()[:2]
        for member in cls:
            if cleaned == member.value:
                return member
        return cls.DE


LANGUAGE_METADATA: dict[str, dict[str, str]] = {
    "de": {"flag": "🇩🇪", "label": "Deutsch"},
    "en": {"flag": "🇬🇧", "label": "English"},
    "fr": {"flag": "🇫🇷", "label": "Français"},
    "es": {"flag": "🇪🇸", "label": "Español"},
    "it": {"flag": "🇮🇹", "label": "Italiano"},
    "ja": {"flag": "🇯🇵", "label": "日本語"},
}


def compute_source_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


@dataclass
class TranslationRecord:
    id: int | None
    source_hash: str
    english_text: str
    target_language: str
    translated_text: str
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EntityFieldTranslation:
    id: int | None
    entity_type: str
    entity_id: int
    field_name: str
    language: str
    text_content: str
    is_outdated: bool = False
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
