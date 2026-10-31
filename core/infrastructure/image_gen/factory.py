from domain.settings.models import ServiceSettings
from infrastructure.image_gen.comfyui import ComfyUIImageGenProvider
from infrastructure.image_gen.interface import ImageGenProvider


def get_image_gen_provider(settings: ServiceSettings) -> ImageGenProvider:
    return ComfyUIImageGenProvider(base_url=settings.comfyui_url)
