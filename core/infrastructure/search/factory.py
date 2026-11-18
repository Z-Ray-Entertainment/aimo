from domain.settings.models import LLMBackend, SearchBackend, ServiceSettings
from infrastructure.search.interface import SearchProvider
from infrastructure.search.stub import (
    DisabledSearchProvider,
    GoogleSearchStubProvider,
    SearXNGSearchStubProvider,
)


def get_search_provider(settings: ServiceSettings) -> SearchProvider:
    if (
        settings.search_backend == SearchBackend.GOOGLE_AI
        and settings.llm_backend == LLMBackend.GOOGLE_AI
    ):
        return GoogleSearchStubProvider(api_key=settings.google_ai_api_key)
    if settings.search_backend == SearchBackend.SEARXNG:
        return SearXNGSearchStubProvider(base_url=settings.searxng_url)
    return DisabledSearchProvider()
