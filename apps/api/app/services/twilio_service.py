from __future__ import annotations

import logging
from urllib.parse import urljoin

from fastapi import Request

from app.core.config import get_settings
from app.providers.voice import get_voice_provider
from app.providers.voice.base import VoiceCallResult
from app.utils.phone import mask_phone

logger = logging.getLogger("app.pavi.voice")

SAY_VOICES = {"en": "Polly.Joanna", "hi": "Polly.Aditi", "mr": "Polly.Aditi"}


class TwilioVoiceService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider = get_voice_provider()

    def public_base(self) -> str:
        return (self.settings.twilio_webhook_base_url or "http://localhost:8000").rstrip("/")

    def twiml_url(self, reminder_id: str) -> str:
        return f"{self.public_base()}{self.settings.api_prefix}/voice/twilio/twiml/{reminder_id}"

    def status_url(self) -> str:
        return f"{self.public_base()}{self.settings.api_prefix}/voice/twilio/status"

    def audio_url(self, key: str) -> str:
        return f"{self.public_base()}{self.settings.api_prefix}/voice/audio/{key}"

    def make_call(self, *, to: str, reminder_id: str) -> VoiceCallResult:
        logger.info("[VOICE_CALL] reminder_id=%s status=initiated to=%s", reminder_id, mask_phone(to))
        return self.provider.make_call(
            to=to,
            twiml_url=self.twiml_url(reminder_id),
            status_callback_url=self.status_url(),
        )

    def generate_twiml(self, *, spoken_text: str, audio_url: str | None, language: str = "en") -> str:
        try:
            from twilio.twiml.voice_response import VoiceResponse

            response = VoiceResponse()
            if audio_url:
                response.play(audio_url)
            else:
                response.say(
                    spoken_text,
                    voice=SAY_VOICES.get(language, "Polly.Joanna"),
                    language=_twilio_lang(language),
                )
            return str(response)
        except ImportError:
            body = f"<Play>{audio_url}</Play>" if audio_url else f"<Say>{_xml_escape(spoken_text)}</Say>"
            return f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'

    def validate_request(self, request: Request, form: dict[str, str]) -> bool:
        if self.settings.voice_call_mode != "live":
            return True
        if not self.settings.twilio_auth_token:
            return False
        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        forwarded = request.headers.get("x-forwarded-proto")
        if forwarded and url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(self.settings.twilio_auth_token)
        return validator.validate(url, form, signature)


def _twilio_lang(language: str) -> str:
    return {"en": "en-IN", "hi": "hi-IN", "mr": "en-IN"}.get(language, "en-IN")


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
