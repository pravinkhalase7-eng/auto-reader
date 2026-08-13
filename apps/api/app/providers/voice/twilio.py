from __future__ import annotations

import logging

from app.core.config import get_settings
from app.providers.voice.base import VoiceCallProvider, VoiceCallResult
from app.utils.phone import mask_phone

logger = logging.getLogger("app.pavi.voice")


class TwilioVoiceProvider(VoiceCallProvider):
    def make_call(self, *, to: str, twiml_url: str, status_callback_url: str) -> VoiceCallResult:
        settings = get_settings()
        if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_phone_number):
            raise RuntimeError("Twilio credentials are not configured")
        from twilio.rest import Client

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        call = client.calls.create(
            to=to,
            from_=settings.twilio_phone_number,
            url=twiml_url,
            method="POST",
            status_callback=status_callback_url,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
        )
        logger.info("[VOICE_CALL] provider=twilio to=%s sid=%s status=%s", mask_phone(to), call.sid, call.status)
        return VoiceCallResult(provider="twilio", status=call.status or "queued", call_sid=call.sid)
