from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import hashlib


class Language(StrEnum):
    EN = "en"
    ZH = "zh"
    HI = "hi"
    ES = "es"
    FR = "fr"
    AR = "ar"
    BN = "bn"
    PT = "pt"
    RU = "ru"
    UR = "ur"
    ID = "id"
    DE = "de"
    JA = "ja"
    TR = "tr"
    KO = "ko"
    VI = "vi"
    IT = "it"
    PL = "pl"
    NL = "nl"
    TH = "th"

    @classmethod
    def resolve(cls, raw: str | "Language") -> "Language":
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, str):
            return cls.EN
        cleaned = raw.strip().lower()[:2]
        for member in cls:
            if cleaned == member.value:
                return member
        return cls.EN


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

SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(LANGUAGE_METADATA.keys())


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
