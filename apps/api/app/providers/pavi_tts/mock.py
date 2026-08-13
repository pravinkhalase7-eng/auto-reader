from __future__ import annotations

import io
import logging
import math
import struct
import wave

from app.providers.pavi_tts.base import TTSAudio, TTSProvider

logger = logging.getLogger("app.pavi.tts")


def _placeholder_wav(duration_s: float = 1.2, sample_rate: int = 8000) -> bytes:
    n = int(duration_s * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n):
            sample = int(8000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            frames += struct.pack("<h", sample)
        wf.writeframes(bytes(frames))
    return buf.getvalue()


class MockTTSProvider(TTSProvider):
    async def synthesize(self, text: str, *, language: str = "en", voice: str | None = None) -> TTSAudio:
        logger.info("[TTS] provider=mock lang=%s chars=%s", language, len(text or ""))
        return TTSAudio(
            audio_bytes=_placeholder_wav(),
            content_type="audio/wav",
            provider="mock",
            voice=voice or "mock",
            language=language,
        )
