"""Lesson-reader TTS: Google Cloud Speech first, then Gemini, then ElevenLabs."""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.providers.pavi_tts.gemini import GeminiTTSProvider
from app.services import google_cloud_tts
from app.services.elevenlabs import elevenlabs_enabled
from app.services.elevenlabs import synthesize as elevenlabs_synthesize

logger = logging.getLogger(__name__)

GEMINI_VOICES: list[dict[str, str]] = [
    {"id": "Kore", "name": "Google Kore", "accent": "Warm", "category": "google"},
    {"id": "Aoede", "name": "Google Aoede", "accent": "Bright", "category": "google"},
    {"id": "Charon", "name": "Google Charon", "accent": "Calm", "category": "google"},
    {"id": "Fenrir", "name": "Google Fenrir", "accent": "Strong", "category": "google"},
    {"id": "Puck", "name": "Google Puck", "accent": "Upbeat", "category": "google"},
    {"id": "default", "name": "Google teacher", "accent": "Warm", "category": "google"},
]


def gemini_tts_available() -> bool:
    return bool(get_settings().resolved_gemini_api_key)


def cloud_voices(language: str = "") -> list[dict[str, str]]:
    if google_cloud_tts.google_cloud_tts_enabled():
        return google_cloud_tts.list_voices(language)
    if gemini_tts_available():
        return [dict(v) for v in GEMINI_VOICES]
    return []


def _gemini_voice_name(voice_id: str) -> str:
    vid = (voice_id or "").strip()
    if not vid or vid in {"default", "google", "elevenlabs", "cloud"}:
        return get_settings().gemini_tts_voice or "Kore"
    known = {v["id"] for v in GEMINI_VOICES if v["id"] != "default"}
    if vid in known:
        return vid
    # Cloud voice ids (en-IN-…) are not Gemini names — use default teacher voice.
    if "-" in vid:
        return get_settings().gemini_tts_voice or "Kore"
    return vid


async def _gemini_speech(
    text: str,
    language: str,
    voice_id: str = "default",
) -> tuple[bytes, str] | None:
    if not gemini_tts_available():
        return None
    lang = (language or "en").split("-")[0].lower()
    if lang not in {"en", "hi", "mr"}:
        lang = "en"
    voice = _gemini_voice_name(voice_id)
    audio = await GeminiTTSProvider().synthesize(
        text,
        language=lang,
        voice=voice,
        speak_verbatim=True,
    )
    return audio.audio_bytes, audio.content_type


async def speak_lesson(
    text: str,
    voice_id: str,
    *,
    speed: str = "normal",
    language: str = "en",
) -> tuple[bytes, str]:
    last_error: AppError | None = None

    # 1) Google Cloud Text-to-Speech (GOOGLE_TTS_API_KEY from ai-code-player)
    if google_cloud_tts.google_cloud_tts_enabled():
        try:
            audio = await google_cloud_tts.synthesize(
                text, voice_id, speed=speed, language=language
            )
            return audio, "audio/mpeg"
        except AppError as exc:
            last_error = exc
            logger.warning("google_cloud_tts_lesson_failed code=%s — trying Gemini", exc.code)

    # 2) Gemini TTS fallback (GOOGLE_AI_API_KEY / GEMINI_API_KEY)
    if gemini_tts_available():
        try:
            gemini = await _gemini_speech(text, language, voice_id=voice_id)
            if gemini:
                return gemini
        except Exception as exc:  # noqa: BLE001
            logger.warning("gemini_lesson_tts_failed err=%r", exc)
            last_error = AppError(
                "Google speech could not read this line right now.",
                code="GOOGLE_TTS_FAILED",
                status_code=502,
            )

    # 3) Optional ElevenLabs
    if elevenlabs_enabled():
        try:
            audio = await elevenlabs_synthesize(text, voice_id, speed=speed, language=language)
            return audio, "audio/mpeg"
        except AppError as exc:
            last_error = exc
            logger.warning("elevenlabs_lesson_failed code=%s", exc.code)

    if last_error and last_error.code not in {
        "NO_GOOGLE_TTS_KEY",
        "GOOGLE_TTS_UNAUTHORIZED",
        "ELEVENLABS_UNAUTHORIZED",
        "NO_ELEVENLABS_KEY",
    }:
        raise last_error
    raise AppError(
        "I couldn't play this in a clear Google voice right now. Check GOOGLE_TTS_API_KEY, then try again.",
        code="TTS_UNAVAILABLE",
        status_code=502,
    )
