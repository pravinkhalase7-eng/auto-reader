"""Lesson-reader TTS: ElevenLabs when the key works, otherwise Gemini."""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.providers.pavi_tts.gemini import GeminiTTSProvider
from app.services.elevenlabs import elevenlabs_enabled, synthesize

logger = logging.getLogger(__name__)

CLOUD_VOICE = {
    "id": "default",
    "name": "Cloud teacher",
    "accent": "",
    "category": "cloud",
}


def gemini_tts_available() -> bool:
    return bool(get_settings().resolved_gemini_api_key)


def cloud_voices() -> list[dict[str, str]]:
    if not gemini_tts_available():
        return []
    return [dict(CLOUD_VOICE)]


async def _gemini_speech(text: str, language: str) -> tuple[bytes, str] | None:
    if not gemini_tts_available():
        return None
    lang = (language or "en").split("-")[0].lower()
    if lang not in {"en", "hi", "mr"}:
        lang = "en"
    audio = await GeminiTTSProvider().synthesize(text, language=lang, speak_verbatim=True)
    return audio.audio_bytes, audio.content_type


async def speak_lesson(
    text: str,
    voice_id: str,
    *,
    speed: str = "normal",
    language: str = "en",
) -> tuple[bytes, str]:
    last_error: AppError | None = None
    if elevenlabs_enabled():
        try:
            audio = await synthesize(text, voice_id, speed=speed, language=language)
            return audio, "audio/mpeg"
        except AppError as exc:
            last_error = exc
            logger.warning("elevenlabs_lesson_failed code=%s — trying Gemini", exc.code)
    try:
        gemini = await _gemini_speech(text, language)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gemini_lesson_tts_failed err=%r", exc)
        gemini = None
    if gemini:
        return gemini
    if last_error and last_error.code not in {"ELEVENLABS_UNAUTHORIZED", "NO_ELEVENLABS_KEY"}:
        raise last_error
    raise AppError(
        "I couldn't play this in a clear voice right now. Try Play again in a moment.",
        code="TTS_UNAVAILABLE",
        status_code=502,
    )
