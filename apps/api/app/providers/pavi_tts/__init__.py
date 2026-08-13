from app.core.config import get_settings
from app.providers.pavi_tts.base import TTSProvider
from app.providers.pavi_tts.gemini import GeminiTTSProvider
from app.providers.pavi_tts.mock import MockTTSProvider


def get_pavi_tts_provider() -> TTSProvider:
    settings = get_settings()
    if settings.resolved_pavi_tts_provider == "gemini" and settings.resolved_gemini_api_key:
        return GeminiTTSProvider()
    return MockTTSProvider()
