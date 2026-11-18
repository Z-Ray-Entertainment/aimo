from infrastructure.search.interface import SearchProvider
from shared.exceptions import InfrastructureError


class DisabledSearchProvider(SearchProvider):
    def search(self, query: str, max_results: int = 5) -> list[dict]:
        return []

    def check_health(self) -> bool:
        return False


class SearXNGSearchStubProvider(SearchProvider):
    """Prepared SearXNG search interface (temporarily disabled / TODO)."""

    def __init__(self, base_url: str) -> None:
        self.base_url: str = (base_url or "").strip().rstrip("/")

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        raise InfrastructureError(
            "Websuche über SearXNG ist aktuell noch vorbereitet (TODO)."
        )

    def check_health(self) -> bool:
        return False


class GoogleSearchStubProvider(SearchProvider):
    """Prepared Google Search Grounding interface (temporarily disabled / TODO)."""

    def __init__(self, api_key: str) -> None:
        self.api_key: str = (api_key or "").strip()

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        raise InfrastructureError(
            "Websuche über Google Search Grounding ist aktuell noch vorbereitet (TODO)."
        )

    def check_health(self) -> bool:
        return False
