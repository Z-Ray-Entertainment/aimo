from pathlib import Path
from typing import ClassVar

from domain.settings.models import ServiceSettings
from infrastructure.image_gen.interface import ImageGenProvider
from shared.exceptions import InfrastructureError


class DisabledImageGenProvider(ImageGenProvider):
    PROVIDER_ID: ClassVar[str] = "disabled"
    DISPLAY_NAME: ClassVar[str] = "Deaktiviert"

    @classmethod
    def is_enabled(cls) -> bool:
        return False

    @classmethod
    def from_settings(cls, settings: ServiceSettings) -> "DisabledImageGenProvider":
        return cls()

    def generate_image(
        self,
        prompt: str,
        reference_images: list[Path],
        negative_prompt: str,
        output_path: Path,
    ) -> Path:
        raise InfrastructureError("Bildgenerierung ist aktuell deaktiviert.")

    def cancel_generation(self, task_id: str) -> None:
        return None

    def check_health(self) -> bool:
        return False
