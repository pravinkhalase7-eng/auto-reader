from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TTSAudio:
    audio_bytes: bytes
    content_type: str
    provider: str
    voice: str
    language: str


class TTSProvider(ABC):
    """Pavi call-audio TTS. Separate from lesson-reader TTS in providers/tts.py."""

    @abstractmethod
    async def synthesize(self, text: str, *, language: str = "en", voice: str | None = None) -> TTSAudio:
        raise NotImplementedError
