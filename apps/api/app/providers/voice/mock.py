from __future__ import annotations

import logging
import uuid

from app.providers.voice.base import VoiceCallProvider, VoiceCallResult
from app.utils.phone import mask_phone

logger = logging.getLogger("app.pavi.voice")


class MockVoiceProvider(VoiceCallProvider):
    def make_call(self, *, to: str, twiml_url: str, status_callback_url: str) -> VoiceCallResult:
        sid = f"CA_MOCK_{uuid.uuid4().hex[:24]}"
        logger.info("[MOCK CALL] Calling %s twiml=%s", mask_phone(to), twiml_url)
        logger.info("[VOICE_CALL] provider=mock to=%s sid=%s status=completed", mask_phone(to), sid)
        return VoiceCallResult(provider="mock", status="completed", call_sid=sid)
