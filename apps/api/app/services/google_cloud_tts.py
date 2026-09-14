"""Google Cloud Text-to-Speech for the lesson reader."""

from __future__ import annotations

import base64
import logging

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

SYNTH_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
SPEED_MAP = {
    "very_slow": 0.75,
    "slow": 0.85,
    "normal": 1.0,
    "fast": 1.15,
}

# Classroom-friendly Neural2 / WaveNet / Chirp voices (en / hi / mr).
STATIC_VOICES: list[dict[str, str]] = [
    {"id": "en-IN-Neural2-A", "name": "Google English A", "accent": "India", "category": "google", "language": "en"},
    {"id": "en-IN-Neural2-C", "name": "Google English C", "accent": "India", "category": "google", "language": "en"},
    {"id": "en-US-Chirp3-HD-Aoede", "name": "Google Chirp Aoede", "accent": "US", "category": "google", "language": "en"},
    {"id": "hi-IN-Neural2-A", "name": "Google Hindi A", "accent": "India", "category": "google", "language": "hi"},
    {"id": "hi-IN-Neural2-D", "name": "Google Hindi D", "accent": "India", "category": "google", "language": "hi"},
    {"id": "mr-IN-Wavenet-A", "name": "Google Marathi", "accent": "India", "category": "google", "language": "mr"},
]

DEFAULT_VOICE = {
    "en": "en-IN-Neural2-A",
    "hi": "hi-IN-Neural2-A",
    "mr": "mr-IN-Wavenet-A",
}


def resolved_google_tts_api_key() -> str:
    settings = get_settings()
    return (
        (settings.google_tts_api_key or "").strip()
        or (settings.google_cloud_api_key or "").strip()
    )


def google_cloud_tts_enabled() -> bool:
    """Enable Cloud Text-to-Speech when a dedicated TTS/Cloud API key is set.

    Note: Gemini keys (AQ.… / GOOGLE_AI_API_KEY) cannot call texttospeech.googleapis.com.
    Use GOOGLE_TTS_API_KEY from ai-code-player (AIza…).
    """
    return bool(resolved_google_tts_api_key())


def speaking_rate(speed: str) -> float:
    return max(0.5, min(1.5, SPEED_MAP.get(speed, 1.0)))


def language_code_for(language: str, voice_id: str = "") -> str:
    vid = (voice_id or "").strip()
    parts = vid.split("-")
    if len(parts) >= 2 and len(parts[0]) in {2, 3} and len(parts[1]) == 2:
        return f"{parts[0]}-{parts[1]}"
    key = (language or "en").split("-")[0].lower()
    return {"hi": "hi-IN", "mr": "mr-IN", "en": "en-IN"}.get(key, "en-IN")


def resolve_voice_id(voice_id: str, language: str) -> str:
    vid = (voice_id or "").strip()
    if vid and vid not in {"default", "google", "elevenlabs", "cloud"}:
        return vid
    key = (language or "en").split("-")[0].lower()
    return DEFAULT_VOICE.get(key, DEFAULT_VOICE["en"])


def list_voices(language: str = "") -> list[dict[str, str]]:
    if not google_cloud_tts_enabled():
        return []
    key = (language or "").split("-")[0].lower()
    rows = []
    for item in STATIC_VOICES:
        if key and item.get("language") and item["language"] != key:
            # Always include English as a general option; filter only when lang is hi/mr.
            if key in {"hi", "mr"} and item["language"] != key:
                continue
        rows.append(
            {
                "id": item["id"],
                "name": item["name"],
                "accent": item.get("accent", ""),
                "category": item.get("category", "google"),
            }
        )
    if not rows:
        rows = [
            {
                "id": item["id"],
                "name": item["name"],
                "accent": item.get("accent", ""),
                "category": item.get("category", "google"),
            }
            for item in STATIC_VOICES
        ]
    # Ensure a stable default id for the UI.
    if not any(r["id"] == "default" for r in rows):
        rows.insert(
            0,
            {
                "id": "default",
                "name": "Google teacher",
                "accent": "India",
                "category": "google",
            },
        )
    return rows


async def synthesize(
    text: str,
    voice_id: str,
    *,
    speed: str = "normal",
    language: str = "en",
) -> bytes:
    api_key = resolved_google_tts_api_key()
    if not api_key:
        raise AppError(
            "Google Cloud speech is not set up yet. Add GOOGLE_CLOUD_API_KEY or GOOGLE_AI_API_KEY.",
            code="NO_GOOGLE_TTS_KEY",
            status_code=502,
        )
    clean = (text or "").strip()
    if not clean:
        raise AppError("There is nothing to read yet.", code="EMPTY_TTS_TEXT")
    if len(clean) > 4000:
        clean = clean[:4000]

    voice_name = resolve_voice_id(voice_id, language)
    lang_code = language_code_for(language, voice_name)
    body = {
        "input": {"text": clean},
        "voice": {"languageCode": lang_code, "name": voice_name},
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": speaking_rate(speed),
        },
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=8.0, read=45.0, write=15.0, pool=8.0)) as client:
            resp = await client.post(SYNTH_URL, params={"key": api_key}, json=body)
    except Exception as exc:  # noqa: BLE001
        logger.warning("google_cloud_tts_request_failed err=%r", exc)
        raise AppError(
            "I couldn't reach Google Cloud speech right now. Try again in a moment.",
            code="GOOGLE_TTS_FAILED",
            status_code=502,
        ) from exc

    if resp.status_code >= 400:
        detail = ""
        try:
            payload = resp.json()
            detail = str((payload.get("error") or {}).get("message") or payload)[:200]
        except Exception:  # noqa: BLE001
            detail = resp.text[:200]
        logger.warning("google_cloud_tts_http status=%s detail=%s", resp.status_code, detail)
        if resp.status_code in {401, 403}:
            raise AppError(
                "This Google API key is not allowed for Cloud Text-to-Speech. Enable the API or use a Cloud TTS key.",
                code="GOOGLE_TTS_UNAUTHORIZED",
                status_code=502,
            )
        raise AppError(
            "Google Cloud speech could not read this line. Try another Google voice, or This device.",
            code="GOOGLE_TTS_FAILED",
            status_code=502,
        )

    try:
        audio_b64 = resp.json().get("audioContent") or ""
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "Google Cloud speech returned an unexpected response.",
            code="GOOGLE_TTS_FAILED",
            status_code=502,
        ) from exc
    if not audio_b64:
        raise AppError(
            "Google Cloud speech returned empty audio.",
            code="GOOGLE_TTS_FAILED",
            status_code=502,
        )
    return base64.b64decode(audio_b64)
