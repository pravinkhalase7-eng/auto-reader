from __future__ import annotations

import io
import logging
import struct
import wave

from app.core.config import get_settings
from app.providers.pavi_tts.base import TTSAudio, TTSProvider

logger = logging.getLogger("app.pavi.tts")

LANGUAGE_CODES = {"en": "en-IN", "hi": "hi-IN", "mr": "mr-IN"}


def pcm16_to_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


class GeminiTTSProvider(TTSProvider):
    async def synthesize(
        self,
        text: str,
        *,
        language: str = "en",
        voice: str | None = None,
        speak_verbatim: bool = False,
    ) -> TTSAudio:
        settings = get_settings()
        api_key = settings.resolved_gemini_api_key
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai is required for Gemini TTS") from exc

        client = genai.Client(api_key=api_key)
        voice_name = voice or settings.gemini_tts_voice
        lang = LANGUAGE_CODES.get(language, "en-IN")
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                language_code=lang,
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                ),
            ),
        )
        spoken = (
            text
            if speak_verbatim or text.lower().startswith("say ")
            else f"Say this in a warm, natural speaking voice: {text}"
        )
        models = [settings.gemini_tts_model, "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]
        last_error: Exception | None = None
        response = None
        used_model = settings.gemini_tts_model
        for model in dict.fromkeys(models):
            try:
                response = client.models.generate_content(model=model, contents=spoken, config=config)
                used_model = model
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning("[TTS] gemini model=%s failed: %s", model, exc)
        if response is None:
            raise RuntimeError("Gemini TTS failed") from last_error
        logger.info("[TTS] gemini model=%s voice=%s", used_model, voice_name)
        data = _extract_audio(response)
        wav = pcm16_to_wav(data)
        logger.info("[TTS] provider=gemini lang=%s bytes=%s", language, len(wav))
        return TTSAudio(
            audio_bytes=wav,
            content_type="audio/wav",
            provider="gemini",
            voice=voice_name,
            language=language,
        )


def _extract_audio(response) -> bytes:
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline is None:
                continue
            data = getattr(inline, "data", None)
            if isinstance(data, bytes):
                return data
            if isinstance(data, str):
                import base64

                return base64.b64decode(data)
    raise RuntimeError("Gemini TTS returned no audio")
