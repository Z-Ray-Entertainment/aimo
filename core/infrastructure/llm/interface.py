from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from domain.settings.models import ModelParameters


class LLMProvider(ABC):
    @abstractmethod
    def generate_stream(
        self, prompt: str, model: str, params: ModelParameters
    ) -> Iterator[str]:
        raise NotImplementedError

    @abstractmethod
    def generate(self, prompt: str, model: str, params: ModelParameters) -> str:
        raise NotImplementedError

    @abstractmethod
    def classify(self, text: str, candidates: list[str], model: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def analyze_image(self, image_path: Path, prompt: str, model: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def pull_model(self, name: str) -> Iterator[dict]:
        raise NotImplementedError

    @abstractmethod
    def delete_model(self, name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def check_health(self) -> bool:
        raise NotImplementedError
