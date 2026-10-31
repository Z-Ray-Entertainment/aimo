from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non-binary"

    @classmethod
    def resolve(cls, raw: str | "Gender") -> "Gender":
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, str):
            raise ValueError(f"Invalid gender value: '{raw}'")
        normalized = raw.strip().lower().replace("_", "-")
        for member in cls:
            if normalized == member.value or normalized.upper() == member.name:
                return member
        raise ValueError(f"Unknown gender: '{raw}'")


@dataclass
class UserPersona:
    id: int | None
    user_id: int
    name: str
    gender: Gender
    portrait_path: str
    description: str
    appearance: str = ""
    is_default: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
