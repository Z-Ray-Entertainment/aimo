import struct
from pathlib import Path

from infrastructure.voice.interface import VoiceTTSProvider
from shared.config import Config
from shared.exceptions import InfrastructureError


class VoiceTTSStubProvider(VoiceTTSProvider):
    def __init__(self, output_dir: Path = Config.UPLOAD_DIR / "generated") -> None:
        self.output_dir: Path = Path(output_dir).resolve()

    def synthesize_speech(
        self, text: str, voice_id: str | None, language: str
    ) -> Path:
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            stub_path = self.output_dir / "tts_stub_silence.wav"
            if not stub_path.is_file():
                stub_path.write_bytes(self._build_silent_wav_bytes())
            return stub_path
        except OSError as exc:
            raise InfrastructureError(
                f"Failed to write stub TTS output file: {exc}"
            ) from exc

    def list_voices(self) -> list[dict]:
        return []

    def check_health(self) -> bool:
        return True

    @staticmethod
    def _build_silent_wav_bytes() -> bytes:
        sample_rate = 8000
        num_channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
        block_align = num_channels * (bits_per_sample // 8)
        data_size = 0
        chunk_size = 36 + data_size
        return struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            chunk_size,
            b"WAVE",
            b"fmt ",
            16,
            1,
            num_channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b"data",
            data_size,
        )
