from app.core.config import get_settings
from app.providers.voice.base import VoiceCallProvider
from app.providers.voice.mock import MockVoiceProvider
from app.providers.voice.twilio import TwilioVoiceProvider


def get_voice_provider() -> VoiceCallProvider:
    settings = get_settings()
    if settings.voice_call_mode == "live":
        return TwilioVoiceProvider()
    return MockVoiceProvider()
