from typing import Any, Type

from shared.exceptions import DomainError


class DomainValidator:
    """Consolidated validation utilities for domain entities and services."""

    @staticmethod
    def validate_positive_user_id(user_id: Any, error_cls: Type[DomainError]) -> int:
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise error_cls("A valid positive user_id is required.")
        return user_id

    @staticmethod
    def validate_required_string(val: Any, field_name: str, error_cls: Type[DomainError]) -> str:
        cleaned = val.strip() if isinstance(val, str) else ""
        if not cleaned:
            raise error_cls(f"{field_name} must not be empty.")
        return cleaned

    @staticmethod
    def normalize_visibility(visibility: Any) -> str:
        if isinstance(visibility, str) and visibility.strip().lower() == "public":
            return "public"
        return "private"

    @staticmethod
    def normalize_optional_id(val: Any) -> int | None:
        if val in (None, "", "0", 0, "world", "none"):
            return None
        try:
            parsed = int(val)
            return parsed if parsed > 0 else None
        except (ValueError, TypeError):
            return None
