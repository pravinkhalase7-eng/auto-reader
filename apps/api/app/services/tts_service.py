from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.providers.pavi_tts import get_pavi_tts_provider
from app.providers.pavi_tts.base import TTSAudio

logger = logging.getLogger("app.pavi.tts")


class TTSService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider = get_pavi_tts_provider()
        self.root = Path(self.settings.storage_root) / "pavi_tts"
        self.root.mkdir(parents=True, exist_ok=True)

    async def synthesize_to_file(self, text: str, *, language: str = "en") -> tuple[TTSAudio, str]:
        audio = await self.provider.synthesize(text, language=language)
        key = f"{uuid4().hex}.wav"
        path = self.root / key
        path.write_bytes(audio.audio_bytes)
        logger.info("[TTS] saved key=%s provider=%s", key, audio.provider)
        return audio, key

    def path_for(self, key: str) -> Path:
        path = (self.root / Path(key).name).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("Invalid audio key")
        return path

    def cleanup(self, key: str | None) -> None:
        if not key:
            return
        path = self.path_for(key)
        try:
            if path.exists():
                path.unlink()
        except OSError:
            logger.warning("[TTS] cleanup_failed key=%s", key)
