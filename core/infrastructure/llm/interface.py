from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from domain.settings.models import ModelParameters, ServiceSettings, TaskAssignment


class LLMProvider(ABC):
    PROVIDER_ID: ClassVar[str] = ""
    DISPLAY_NAME: ClassVar[str] = ""
    BADGE_LABEL: ClassVar[str] = ""
    DESCRIPTION: ClassVar[str] = ""
    DEFAULT_MODEL_ROLES: ClassVar[dict[str, dict[str, str]]] = {}

    @classmethod
    def get_recommended_models(cls) -> dict[str, dict[str, str]]:
        return {role: dict(info) for role, info in cls.DEFAULT_MODEL_ROLES.items()}

    @classmethod
    def get_recommended_task_models(cls) -> dict[str, str]:
        return {role: info["model"] for role, info in cls.DEFAULT_MODEL_ROLES.items()}

    @classmethod
    def get_recommended_task_assignment(cls) -> TaskAssignment:
        rec = cls.get_recommended_task_models()
        return TaskAssignment(
            roleplay_model=rec.get("roleplay", ""),
            memory_model=rec.get("memory", ""),
            assistant_model=rec.get("assistant", ""),
            vision_model=rec.get("vision", ""),
            classification_model=rec.get("classification", ""),
        )

    @classmethod
    def get_unique_recommended_models(cls) -> list[str]:
        return list(dict.fromkeys(cls.get_recommended_task_models().values()))

    @classmethod
    def supports_model_management(cls) -> bool:
        return False

    @classmethod
    def is_model_compatible(cls, model_name: str) -> bool:
        return bool(isinstance(model_name, str) and model_name.strip())

    @classmethod
    def get_default_config(cls) -> dict[str, str]:
        return {}

    @classmethod
    def validate_active_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
        clear_secret: bool = False,
    ) -> dict[str, str]:
        return dict(existing)

    @classmethod
    def validate_inactive_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
        clear_secret: bool = False,
    ) -> dict[str, str]:
        return dict(existing)

    @classmethod
    @abstractmethod
    def from_settings(cls, settings: ServiceSettings) -> "LLMProvider":
        raise NotImplementedError

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        model: str,
        params: ModelParameters,
        stop: list[str] | None = None,
        think: bool | None = None,
    ) -> Iterator[str]:
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        prompt: str,
        model: str,
        params: ModelParameters,
        stop: list[str] | None = None,
        format: str | dict | None = None,
        think: bool | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def classify(self, text: str, candidates: list[str], model: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def classify_turn(
        self,
        text: str,
        emotion_candidates: list[str] | None,
        location_candidates: list[str] | None,
        model: str,
    ) -> tuple[str, str | None]:
        raise NotImplementedError

    @abstractmethod
    def analyze_image(self, image_path: Path, prompt: str, model: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[str]:
        raise NotImplementedError

    def list_image_models(self) -> list[str]:
        return []

    def list_model_catalog(self) -> tuple[list[str], list[str]]:
        return self.list_models(), self.list_image_models()

    @abstractmethod
    def pull_model(self, name: str) -> Iterator[dict]:
        raise NotImplementedError

    @abstractmethod
    def delete_model(self, name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def check_health(self) -> bool:
        raise NotImplementedError

    def get_model_context_length(self, model: str) -> int | None:
        return None

    def format_stream_error(self, exc: Exception, model: str) -> str:
        return f"KI-Verbindungsfehler ({model}): {exc}"
