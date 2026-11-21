from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.base import OwnedEntityMixin, ResolvableStrEnum, utc_now


class Gender(ResolvableStrEnum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non-binary"

    @classmethod
    def _normalize_raw(cls, raw: str) -> str:
        return raw.strip().lower().replace("_", "-")

    @classmethod
    def resolve(cls, raw: str | "Gender") -> "Gender":
        return cls.resolve_value(raw, strict=True)


MAX_PERSONA_DESCRIPTION_LENGTH: int = 1200


@dataclass
class UserPersona(OwnedEntityMixin):
    id: int | None
    user_id: int
    name: str
    gender: Gender
    portrait_path: str
    description: str
    appearance: str = ""
    origin_language: str = "en"
    is_default: bool = False
    created_at: datetime = field(default_factory=utc_now)
