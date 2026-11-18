from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from domain.settings.models import ServiceSettings


class SearchProvider(ABC):
    PROVIDER_ID: ClassVar[str] = ""
    DISPLAY_NAME: ClassVar[str] = ""
    REQUIRES_LLM_BACKEND: ClassVar[str | None] = None

    @classmethod
    def get_default_config(cls) -> dict[str, str]:
        return {}

    @classmethod
    def validate_active_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
    ) -> dict[str, str]:
        return dict(existing)

    @classmethod
    def validate_inactive_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
    ) -> dict[str, str]:
        return dict(existing)

    @classmethod
    @abstractmethod
    def from_settings(cls, settings: ServiceSettings) -> "SearchProvider":
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def check_health(self) -> bool:
        raise NotImplementedError
