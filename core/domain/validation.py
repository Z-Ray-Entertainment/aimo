import re
from typing import Any, Iterable, Type

from shared.exceptions import DomainError

_THINKING_BLOCK_RE = re.compile(
    r"<(?:think|thought|reasoning)>.*?</(?:think|thought|reasoning)>",
    re.IGNORECASE | re.DOTALL,
)


class DomainValidator:
    """Consolidated validation utilities for domain entities and services."""

    @staticmethod
    def validate_positive_id(value: Any, field_name: str, error_cls: Type[DomainError]) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise error_cls(f"A valid positive {field_name} is required.")
        return value

    @staticmethod
    def validate_positive_user_id(user_id: Any, error_cls: Type[DomainError]) -> int:
        return DomainValidator.validate_positive_id(user_id, "user_id", error_cls)

    @staticmethod
    def validate_required_string(val: Any, field_name: str, error_cls: Type[DomainError]) -> str:
        cleaned = val.strip() if isinstance(val, str) else ""
        if not cleaned:
            raise error_cls(f"{field_name} must not be empty.")
        return cleaned

    @staticmethod
    def validate_int_range(
        value: Any,
        field_name: str,
        min_val: int,
        max_val: int,
        error_cls: Type[DomainError],
    ) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < min_val or value > max_val:
            raise error_cls(f"{field_name} must be an integer between {min_val} and {max_val}.")
        return value

    @staticmethod
    def normalize_visibility(visibility: Any) -> str:
        if isinstance(visibility, str) and visibility.strip().lower() == "public":
            return "public"
        return "private"

    @staticmethod
    def normalize_collaborator_tags(tags: Iterable[str] | None) -> list[str]:
        if not tags:
            return []
        return [t.strip().lower() for t in tags if isinstance(t, str) and t.strip()]

    @staticmethod
    def strip_llm_thinking_tags(text: str) -> str:
        return _THINKING_BLOCK_RE.sub("", text or "").strip()

    @staticmethod
    def normalize_optional_id(val: Any) -> int | None:
        if val in (None, "", "0", 0, "world", "none"):
            return None
        try:
            parsed = int(val)
            return parsed if parsed > 0 else None
        except (ValueError, TypeError):
            return None
