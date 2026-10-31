from abc import ABC, abstractmethod
from pathlib import Path


class ImageGenProvider(ABC):
    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        reference_images: list[Path],
        negative_prompt: str,
        output_path: Path,
    ) -> Path:
        raise NotImplementedError

    @abstractmethod
    def cancel_generation(self, task_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def check_health(self) -> bool:
        raise NotImplementedError
