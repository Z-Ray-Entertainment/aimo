from domain.settings.exceptions import InvalidSearchBackendError
from domain.settings.models import ServiceSettings
from infrastructure.search.interface import SearchProvider
from infrastructure.search.stub import (
    DisabledSearchProvider,
    GoogleSearchStubProvider,
    SearXNGSearchStubProvider,
)

SEARCH_PROVIDER_CLASSES: dict[str, type[SearchProvider]] = {
    GoogleSearchStubProvider.PROVIDER_ID: GoogleSearchStubProvider,
    SearXNGSearchStubProvider.PROVIDER_ID: SearXNGSearchStubProvider,
    DisabledSearchProvider.PROVIDER_ID: DisabledSearchProvider,
}


def get_search_provider_class(backend: str) -> type[SearchProvider]:
    cleaned = (backend or "").strip().lower()
    provider_cls = SEARCH_PROVIDER_CLASSES.get(cleaned)
    if provider_cls is None:
        raise InvalidSearchBackendError(f"Unsupported search backend: '{backend}'")
    return provider_cls


def get_search_provider(settings: ServiceSettings) -> SearchProvider:
    backend = settings.search_backend or DisabledSearchProvider.PROVIDER_ID
    provider_cls = get_search_provider_class(backend)
    if (
        provider_cls.REQUIRES_LLM_BACKEND is not None
        and provider_cls.REQUIRES_LLM_BACKEND != settings.llm_backend
    ):
        return DisabledSearchProvider.from_settings(settings)
    return provider_cls.from_settings(settings)
