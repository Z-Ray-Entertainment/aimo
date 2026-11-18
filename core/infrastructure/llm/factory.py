from typing import Any

from domain.settings.models import LLMBackend, ServiceSettings
from domain.settings.services import SettingsService
from infrastructure.llm.google_ai import GoogleAILLMProvider
from infrastructure.llm.interface import LLMProvider
from infrastructure.llm.ollama import OllamaLLMProvider
from shared.config import Config
from shared.exceptions import AimoError


def get_llm_provider(settings: ServiceSettings) -> LLMProvider:
    if settings.llm_backend == LLMBackend.GOOGLE_AI:
        return GoogleAILLMProvider(
            api_key=settings.google_ai_api_key,
            base_url=Config.GOOGLE_AI_BASE_URL,
        )
    return OllamaLLMProvider(base_url=settings.ollama_url)


def probe_llm_backend(
    backend: LLMBackend | str,
    ollama_url: str = "",
    google_ai_api_key: str = "",
) -> dict[str, Any]:
    """Validate credentials/endpoint and return available models without exposing secrets."""
    try:
        resolved = LLMBackend.resolve(backend)
        if resolved == LLMBackend.GOOGLE_AI:
            cleaned_key = SettingsService._validate_api_key(
                "google_ai_api_key", google_ai_api_key
            )
            provider = GoogleAILLMProvider(
                api_key=cleaned_key,
                base_url=Config.GOOGLE_AI_BASE_URL,
                request_timeout=(5.0, 15.0),
            )
            text_models, image_models = provider.list_model_catalog()
            return {
                "healthy": True,
                "backend": resolved.value,
                "models": text_models,
                "image_models": image_models,
            }

        cleaned_url = SettingsService._validate_url("ollama_url", ollama_url)
        ollama_provider = OllamaLLMProvider(
            base_url=cleaned_url,
            request_timeout=(5.0, 15.0),
        )
        models = ollama_provider.list_models()
        return {
            "healthy": True,
            "backend": resolved.value,
            "models": models,
            "image_models": [],
        }
    except AimoError as exc:
        return {
            "healthy": False,
            "backend": str(backend),
            "models": [],
            "image_models": [],
            "error": str(exc),
        }
