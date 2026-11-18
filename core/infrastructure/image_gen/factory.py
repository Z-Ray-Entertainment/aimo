from domain.settings.exceptions import InvalidImageGenBackendError
from domain.settings.models import ServiceSettings
from infrastructure.image_gen.comfyui import ComfyUIImageGenProvider
from infrastructure.image_gen.disabled import DisabledImageGenProvider
from infrastructure.image_gen.google_ai import GoogleAIImageGenProvider
from infrastructure.image_gen.interface import ImageGenProvider

IMAGE_GEN_PROVIDER_CLASSES: dict[str, type[ImageGenProvider]] = {
    GoogleAIImageGenProvider.PROVIDER_ID: GoogleAIImageGenProvider,
    ComfyUIImageGenProvider.PROVIDER_ID: ComfyUIImageGenProvider,
    DisabledImageGenProvider.PROVIDER_ID: DisabledImageGenProvider,
}


def get_image_gen_provider_class(backend: str) -> type[ImageGenProvider]:
    cleaned = (backend or "").strip().lower()
    provider_cls = IMAGE_GEN_PROVIDER_CLASSES.get(cleaned)
    if provider_cls is None:
        raise InvalidImageGenBackendError(
            f"Unsupported image generation backend: '{backend}'"
        )
    return provider_cls


def get_image_gen_provider(settings: ServiceSettings) -> ImageGenProvider:
    backend = settings.image_gen_backend or DisabledImageGenProvider.PROVIDER_ID
    provider_cls = get_image_gen_provider_class(backend)
    if (
        provider_cls.REQUIRES_LLM_BACKEND is not None
        and provider_cls.REQUIRES_LLM_BACKEND != settings.llm_backend
    ):
        return DisabledImageGenProvider.from_settings(settings)
    return provider_cls.from_settings(settings)
