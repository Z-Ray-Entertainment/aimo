from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, ClassVar, Protocol, Self


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResolvableStrEnum(StrEnum):
    @classmethod
    def _get_aliases(cls) -> dict[str, str]:
        return {}

    @classmethod
    def _normalize_raw(cls, raw: str) -> str:
        return raw.strip().lower()

    @classmethod
    def resolve_value(
        cls,
        raw: Any,
        *,
        default: Self | None = None,
        strict: bool = False,
    ) -> Self:
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, str):
            if strict:
                raise ValueError(f"Invalid {cls.__name__} value: '{raw}'")
            assert default is not None
            return default
        cleaned = cls._normalize_raw(raw)
        cleaned = cls._get_aliases().get(cleaned, cleaned)
        for member in cls:
            if cleaned == member.value or cleaned.upper() == member.name:
                return member
        if strict:
            raise ValueError(f"Unknown {cls.__name__}: '{raw}'")
        assert default is not None
        return default


class OwnedEntityMixin:
    user_id: int

    def is_visible_to_user(self, user_id: int, is_admin: bool = False) -> bool:
        return self.user_id == user_id or is_admin

    def is_editable_by_user(self, user_id: int, is_admin: bool = False) -> bool:
        return self.user_id == user_id or is_admin

    def is_deletable_by_user(self, user_id: int, is_admin: bool = False) -> bool:
        return self.user_id == user_id or is_admin


class PublishableEntityMixin(OwnedEntityMixin):
    visibility: str
    collaborator_creator_tags: list[str]

    def is_visible_to_user(self, user_id: int, is_admin: bool = False) -> bool:
        return self.visibility == "public" or self.user_id == user_id or is_admin

    def is_editable_by_user(
        self,
        user_id: int,
        is_admin: bool = False,
        creator_tag: str | None = None,
    ) -> bool:
        if self.user_id == user_id or is_admin:
            return True
        if creator_tag and creator_tag in self.collaborator_creator_tags:
            return True
        return False


class TextGenerationProvider(Protocol):
    def generate(self, prompt: str, model: str, params: Any = None, **kwargs: Any) -> str:
        ...
