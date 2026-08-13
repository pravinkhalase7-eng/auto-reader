"""ElevenLabs TTS — optional extra voices, used only when ELEVENLABS_API_KEY is set."""

from __future__ import annotations

import logging
import time

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

VOICES_URL = "https://api.elevenlabs.io/v1/voices"
SPEAK_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
SPEED_MAP = {
    "very_slow": 0.75,
    "slow": 0.85,
    "normal": 1.0,
    "fast": 1.15,
}
# Free ElevenLabs API keys cannot speak Voice Library / professional copies.
API_VOICE_CATEGORIES = {"premade", "cloned", "generated"}
TEACHER_VOICE_HINTS = ("alice", "george", "jessica", "matilda", "sarah", "lily")

_voices_cache: tuple[float, list[dict[str, str]]] | None = None
CACHE_SECONDS = 300
_key_rejected = False


def sanitize_secret(raw: str) -> str:
    key = (raw or "").strip().strip('"').strip("'")
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    key = key.split("#", 1)[0].strip()
    return key.split()[0] if key else ""


def reset_elevenlabs_status() -> None:
    global _key_rejected, _voices_cache
    _key_rejected = False
    _voices_cache = None


def mark_elevenlabs_key_rejected() -> None:
    global _key_rejected, _voices_cache
    _key_rejected = True
    _voices_cache = None
    logger.warning("elevenlabs_key_rejected — lesson reading will use Gemini instead")


def _api_key() -> str:
    return sanitize_secret(get_settings().elevenlabs_api_key)


def elevenlabs_enabled() -> bool:
    if _key_rejected:
        return False
    return bool(_api_key())


def elevenlabs_speed(speed: str) -> float:
    value = SPEED_MAP.get(speed, 1.0)
    return max(0.7, min(1.2, value))


def elevenlabs_language_code(language: str) -> str | None:
    key = (language or "en").split("-")[0].lower()
    return {"mr": "mr", "hi": "hi", "en": "en"}.get(key)


def elevenlabs_model_for_language(language: str, configured: str = "") -> str:
    """Marathi needs Eleven v3; multilingual v2 only has Hindi among Indic languages."""
    key = (language or "en").split("-")[0].lower()
    if key == "mr":
        return "eleven_v3"
    return configured or "eleven_multilingual_v2"


def elevenlabs_allows_model_fallback(language: str) -> bool:
    """Do not fall back to multilingual v2 for Marathi — it would pronounce Hindi."""
    return (language or "en").split("-")[0].lower() != "mr"


def _speak_body(text: str, model: str, speed: str, language_code: str | None) -> dict[str, object]:
    settings_body: dict[str, object] = {
        "stability": 0.5 if model == "eleven_v3" else 0.45,
        "similarity_boost": 0.75,
        "speed": elevenlabs_speed(speed),
    }
    if model != "eleven_v3":
        settings_body["style"] = 0.15
    body: dict[str, object] = {
        "text": text,
        "model_id": model,
        "voice_settings": settings_body,
    }
    if language_code and model != "eleven_multilingual_v2":
        body["language_code"] = language_code
    return body


def voice_usable_on_api(item: dict) -> bool:
    category = str(item.get("category") or "").strip().lower()
    sharing = item.get("sharing") if isinstance(item.get("sharing"), dict) else {}
    if category == "professional" or sharing.get("status") == "copied":
        return False
    return category in API_VOICE_CATEGORIES or not category


def prefer_teacher_voices(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    def sort_key(row: dict[str, str]) -> tuple[int, int, str]:
        name = row.get("name", "").lower()
        for index, hint in enumerate(TEACHER_VOICE_HINTS):
            if hint in name:
                return (0, index, name)
        return (1, 0, name)

    return sorted(rows, key=sort_key)


def elevenlabs_error_message(status: int, detail: str) -> tuple[str, str]:
    text = (detail or "").lower()
    if status == 401 or status == 403 or "invalid api key" in text or "missing api key" in text:
        mark_elevenlabs_key_rejected()
        return (
            "The ElevenLabs key on this server is not accepted. Check ELEVENLABS_API_KEY, then try again.",
            "ELEVENLABS_UNAUTHORIZED",
        )
    if "quota" in text or "credits" in text or "limit" in text:
        return (
            "This ElevenLabs account is out of speaking credits. Try a browser voice, or add credits in ElevenLabs.",
            "ELEVENLABS_QUOTA",
        )
    if "library" in text or "free users cannot" in text:
        return (
            "That ElevenLabs voice is from the Voice Library. A free key can only use classroom voices like Alice or George.",
            "ELEVENLABS_LIBRARY_VOICE",
        )
    return (
        "I couldn't use the ElevenLabs voice this time. Try another classroom voice, or the browser voice.",
        "ELEVENLABS_FAILED",
    )


def _headers() -> dict[str, str]:
    key = _api_key()
    if not key:
        raise AppError(
            "ElevenLabs is not set up on this server yet. Add ELEVENLABS_API_KEY, then try again.",
            code="NO_ELEVENLABS_KEY",
        )
    return {"xi-api-key": key, "Content-Type": "application/json", "Accept": "application/json"}


def _response_detail(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
        detail = payload.get("detail")
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("detail") or "")[:180]
        if isinstance(detail, str):
            return detail[:180]
        return str(payload.get("message") or "")[:180]
    except Exception:
        return resp.text[:180]


async def list_voices() -> list[dict[str, str]]:
    global _voices_cache
    if not elevenlabs_enabled():
        return []
    now = time.monotonic()
    if _voices_cache and now - _voices_cache[0] < CACHE_SECONDS:
        return _voices_cache[1]
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(VOICES_URL, headers=_headers())
        if resp.status_code >= 400:
            logger.warning("elevenlabs_voices_http status=%s", resp.status_code)
            if resp.status_code in {401, 403}:
                mark_elevenlabs_key_rejected()
            return []
        rows = []
        for item in resp.json().get("voices") or []:
            if not voice_usable_on_api(item):
                continue
            voice_id = str(item.get("voice_id") or "").strip()
            name = str(item.get("name") or "").strip()
            if not voice_id or not name:
                continue
            labels = item.get("labels") or {}
            accent = str(labels.get("accent") or labels.get("language") or "").strip()
            rows.append(
                {
                    "id": voice_id,
                    "name": name.split(" - ")[0].strip() or name,
                    "accent": accent,
                    "category": str(item.get("category") or "premade"),
                }
            )
        rows = prefer_teacher_voices(rows)
        _voices_cache = (now, rows)
        return rows
    except Exception as exc:  # noqa: BLE001
        logger.warning("elevenlabs_voices_failed err=%r", exc)
        return []


async def _post_speech(client: httpx.AsyncClient, voice_id: str, body: dict[str, object]) -> httpx.Response:
    headers = {**_headers(), "Accept": "audio/mpeg"}
    url = SPEAK_URL.format(voice_id=voice_id)
    resp = await client.post(url, headers=headers, json=body)
    if resp.status_code == 400 and "speed" in str(resp.text).lower():
        settings_body = dict(body["voice_settings"])  # type: ignore[arg-type]
        settings_body.pop("speed", None)
        body = {**body, "voice_settings": settings_body}
        resp = await client.post(url, headers=headers, json=body)
    return resp


async def synthesize(text: str, voice_id: str, *, speed: str = "normal", language: str = "en") -> bytes:
    settings = get_settings()
    clean = (text or "").strip()
    if not clean:
        raise AppError("There is nothing to read yet.", code="EMPTY_TTS_TEXT")
    if len(clean) > 4000:
        clean = clean[:4000]
    fallback = settings.elevenlabs_voice_id
    vid = (voice_id or "").strip() or fallback
    if vid in {"default", "elevenlabs"}:
        vid = fallback
    lang_code = elevenlabs_language_code(language)
    primary_model = elevenlabs_model_for_language(language, settings.elevenlabs_model)
    fallback_model = settings.elevenlabs_model or "eleven_multilingual_v2"
    attempts = [_speak_body(clean, primary_model, speed, lang_code)]
    if elevenlabs_allows_model_fallback(language) and primary_model != fallback_model:
        attempts.append(_speak_body(clean, fallback_model, speed, None))
    resp: httpx.Response | None = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=60.0, write=20.0, pool=10.0)) as client:
        for body in attempts:
            resp = await _post_speech(client, vid, body)
            if resp.status_code < 400:
                break
            detail = _response_detail(resp)
            logger.warning(
                "elevenlabs_speak_http status=%s model=%s detail=%s",
                resp.status_code,
                body.get("model_id"),
                detail,
            )
            if vid != fallback and ("library" in detail.lower() or "free users cannot" in detail.lower()):
                logger.info("elevenlabs_retry_premade voice_id=%s", fallback)
                resp = await _post_speech(client, fallback, body)
                if resp.status_code < 400:
                    break
    if resp is None or resp.status_code >= 400:
        detail = _response_detail(resp) if resp is not None else ""
        message, code = elevenlabs_error_message(resp.status_code if resp is not None else 502, detail)
        raise AppError(message, code=code, status_code=502)
    return resp.content
