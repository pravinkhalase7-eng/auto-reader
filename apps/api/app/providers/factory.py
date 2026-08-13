from functools import lru_cache

from app.core.config import get_settings
from app.providers.ai import GeminiProvider, LocalAIProvider, OpenAIProvider
from app.providers.base import AIProvider, OCRProvider, StorageProvider, TTSProvider
from app.providers.ocr import GoogleOCRProvider, LocalOCRProvider, OpenAIOCRProvider
from app.providers.storage import LocalStorageProvider, S3StorageProvider
from app.providers.tts import GoogleTTSProvider, LocalTTSProvider, OpenAITTSProvider


@lru_cache
def get_ocr_provider() -> OCRProvider:
    settings = get_settings()
    mapping = {
        "local": LocalOCRProvider,
        "google": GoogleOCRProvider,
        "openai": OpenAIOCRProvider,
    }
    return mapping.get(settings.ocr_provider, LocalOCRProvider)()


@lru_cache
def get_ai_provider() -> AIProvider:
    settings = get_settings()
    mapping = {
        "local": LocalAIProvider,
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
    }
    return mapping.get(settings.ai_provider, LocalAIProvider)()


@lru_cache
def get_tts_provider() -> TTSProvider:
    settings = get_settings()
    mapping = {
        "local": LocalTTSProvider,
        "browser": LocalTTSProvider,
        "google": GoogleTTSProvider,
        "openai": OpenAITTSProvider,
        "gemini": LocalTTSProvider,
        "mock": LocalTTSProvider,
    }
    return mapping.get(settings.tts_provider, LocalTTSProvider)()


@lru_cache
def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    if settings.storage_provider == "s3":
        return S3StorageProvider()
    return LocalStorageProvider()
