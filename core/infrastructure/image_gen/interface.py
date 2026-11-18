from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from domain.settings.models import ServiceSettings


class ImageGenProvider(ABC):
    PROVIDER_ID: ClassVar[str] = ""
    DISPLAY_NAME: ClassVar[str] = ""
    REQUIRES_LLM_BACKEND: ClassVar[str | None] = None
    RECOMMENDED_MODEL: ClassVar[str | None] = None

    @classmethod
    def is_enabled(cls) -> bool:
        return True

    @classmethod
    def get_recommended_model(cls) -> str | None:
        return cls.RECOMMENDED_MODEL

    @classmethod
    def get_default_config(cls) -> dict[str, str]:
        return {}

    @classmethod
    def validate_active_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
    ) -> dict[str, str]:
        return dict(existing)

    @classmethod
    def validate_inactive_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
    ) -> dict[str, str]:
        return dict(existing)

    @classmethod
    @abstractmethod
    def from_settings(cls, settings: ServiceSettings) -> "ImageGenProvider":
        raise NotImplementedError

    def build_scene_prompt_instruction(
        self,
        diffuser_prompt: str,
        character_summary: str,
        persona_summary: str,
        location_desc: str,
        scene_text: str,
    ) -> str:
        return (
            f"{diffuser_prompt}\n\n"
            f"Character: {character_summary}\n"
            f"Player Persona Appearance: {persona_summary}\n"
            f"Location: {location_desc}\n"
            f"Recent Scene:\n{scene_text}"
        )

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
