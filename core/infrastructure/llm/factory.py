from domain.settings.models import ServiceSettings
from infrastructure.llm.interface import LLMProvider
from infrastructure.llm.ollama import OllamaLLMProvider


def get_llm_provider(settings: ServiceSettings) -> LLMProvider:
    return OllamaLLMProvider(base_url=settings.ollama_url)
