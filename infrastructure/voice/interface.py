from abc import ABC, abstractmethod
from pathlib import Path


class VoiceTTSProvider(ABC):
    @abstractmethod
    def synthesize_speech(
        self, text: str, voice_id: str | None, language: str
    ) -> Path:
        raise NotImplementedError

    @abstractmethod
    def list_voices(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def check_health(self) -> bool:
        raise NotImplementedError
