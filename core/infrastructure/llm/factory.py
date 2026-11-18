from typing import Any

from domain.settings.exceptions import InvalidLLMBackendError
from domain.settings.models import ServiceSettings
from infrastructure.llm.google_ai import GoogleAILLMProvider
from infrastructure.llm.interface import LLMProvider
from infrastructure.llm.ollama import OllamaLLMProvider
from shared.exceptions import AimoError

LLM_PROVIDER_CLASSES: dict[str, type[LLMProvider]] = {
    OllamaLLMProvider.PROVIDER_ID: OllamaLLMProvider,
    GoogleAILLMProvider.PROVIDER_ID: GoogleAILLMProvider,
}


def get_llm_provider_class(backend: str) -> type[LLMProvider]:
    cleaned = (backend or "").strip().lower()
    provider_cls = LLM_PROVIDER_CLASSES.get(cleaned)
    if provider_cls is None:
        raise InvalidLLMBackendError(f"Unsupported LLM backend: '{backend}'")
    return provider_cls


def get_llm_provider(settings: ServiceSettings) -> LLMProvider:
    backend = settings.llm_backend or OllamaLLMProvider.PROVIDER_ID
    provider_cls = get_llm_provider_class(backend)
    return provider_cls.from_settings(settings)


def probe_llm_backend(
    backend: str,
    submitted_config: dict[str, str] | None = None,
    existing_config: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Validate credentials/endpoint and return available models without exposing secrets."""
    try:
        provider_cls = get_llm_provider_class(backend)
        validated_cfg = provider_cls.validate_active_config(
            submitted_config or {},
            existing_config or {},
        )
        temp_settings = ServiceSettings(llm_backend=provider_cls.PROVIDER_ID)
        temp_settings.set_llm_config(provider_cls.PROVIDER_ID, validated_cfg)
        provider = provider_cls.from_settings(temp_settings)
        provider.request_timeout = (5.0, 15.0)
        models, image_models = provider.list_model_catalog()
        return {
            "healthy": True,
            "backend": provider_cls.PROVIDER_ID,
            "models": models,
            "image_models": image_models,
        }
    except AimoError as exc:
        return {
            "healthy": False,
            "backend": str(backend),
            "models": [],
            "image_models": [],
            "error": str(exc),
        }
