"""Speech-to-text lives in the browser for MVP (Web Speech API)."""

from __future__ import annotations


class SpeechService:
    """Backend STT is reserved for future GoogleSpeechProvider / phone streams."""

    provider = "browser"

    def describe(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "note": "Microphone audio is transcribed in the browser and only the transcript is sent to Pavi.",
        }
