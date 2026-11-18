from pathlib import Path

from infrastructure.image_gen.interface import ImageGenProvider
from shared.exceptions import InfrastructureError


class DisabledImageGenProvider(ImageGenProvider):
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
