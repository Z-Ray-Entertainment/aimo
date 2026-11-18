from domain.settings.models import ImageGenBackend, LLMBackend, ServiceSettings
from infrastructure.image_gen.comfyui import ComfyUIImageGenProvider
from infrastructure.image_gen.disabled import DisabledImageGenProvider
from infrastructure.image_gen.google_ai import GoogleAIImageGenProvider
from infrastructure.image_gen.interface import ImageGenProvider
from shared.config import Config


def get_image_gen_provider(settings: ServiceSettings) -> ImageGenProvider:
    if settings.image_gen_backend == ImageGenBackend.DISABLED:
        return DisabledImageGenProvider()
    if (
        settings.image_gen_backend == ImageGenBackend.GOOGLE_AI
        and settings.llm_backend == LLMBackend.GOOGLE_AI
    ):
        return GoogleAIImageGenProvider(
            api_key=settings.google_ai_api_key,
            model=settings.google_ai_image_model,
            base_url=Config.GOOGLE_AI_BASE_URL,
        )
    if settings.image_gen_backend == ImageGenBackend.COMFYUI:
        return ComfyUIImageGenProvider(base_url=settings.comfyui_url)
    return DisabledImageGenProvider()
