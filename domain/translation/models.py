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
