from typing import ClassVar

from domain.settings.models import ServiceSettings
from infrastructure.http_utils import UrlBackendConfigMixin
from infrastructure.search.interface import SearchProvider
from shared.config import Config
from shared.exceptions import InfrastructureError


class DisabledSearchProvider(SearchProvider):
    PROVIDER_ID: ClassVar[str] = "disabled"
    DISPLAY_NAME: ClassVar[str] = "Deaktiviert"

    @classmethod
    def from_settings(cls, settings: ServiceSettings) -> "DisabledSearchProvider":
        return cls()

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        return []

    def check_health(self) -> bool:
        return False


class SearXNGSearchStubProvider(UrlBackendConfigMixin, SearchProvider):
    """Prepared SearXNG search interface (temporarily disabled / TODO)."""

    PROVIDER_ID: ClassVar[str] = "searxng"
    DISPLAY_NAME: ClassVar[str] = "SearXNG (Lokal)"
    DEFAULT_BASE_URL: ClassVar[str] = Config.DEFAULT_SEARXNG_URL
    URL_FIELD_NAME: ClassVar[str] = "searxng_url"

    @classmethod
    def from_settings(cls, settings: ServiceSettings) -> "SearXNGSearchStubProvider":
        cfg = settings.get_search_config(cls.PROVIDER_ID)
        return cls(base_url=cfg.get("base_url") or cls.DEFAULT_BASE_URL)

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url: str = (base_url or "").strip().rstrip("/")

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        raise InfrastructureError(
            "Websuche über SearXNG ist aktuell noch vorbereitet (TODO)."
        )

    def check_health(self) -> bool:
        return False


class GoogleSearchStubProvider(SearchProvider):
    """Prepared Google Search Grounding interface (temporarily disabled / TODO)."""

    PROVIDER_ID: ClassVar[str] = "google_ai"
    DISPLAY_NAME: ClassVar[str] = "Google Search"
    REQUIRES_LLM_BACKEND: ClassVar[str | None] = "google_ai"

    @classmethod
    def from_settings(cls, settings: ServiceSettings) -> "GoogleSearchStubProvider":
        llm_cfg = settings.get_llm_config(cls.REQUIRES_LLM_BACKEND)
        return cls(api_key=llm_cfg.get("api_key") or Config.DEFAULT_GOOGLE_AI_API_KEY)

    def __init__(self, api_key: str = "") -> None:
        self.api_key: str = (api_key or "").strip()

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        raise InfrastructureError(
            "Websuche über Google Search Grounding ist aktuell noch vorbereitet (TODO)."
        )

    def check_health(self) -> bool:
        return False
