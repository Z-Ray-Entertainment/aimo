from domain.settings.models import ServiceSettings
from infrastructure.voice.interface import VoiceTTSProvider
from infrastructure.voice.stub import VoiceTTSStubProvider


def get_voice_provider(settings: ServiceSettings | None = None) -> VoiceTTSProvider:
    return VoiceTTSStubProvider()
