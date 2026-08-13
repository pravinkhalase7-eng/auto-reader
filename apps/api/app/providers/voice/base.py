from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VoiceCallResult:
    provider: str
    status: str
    call_sid: str | None = None
    error: str | None = None


class VoiceCallProvider(ABC):
    @abstractmethod
    def make_call(
        self,
        *,
        to: str,
        twiml_url: str,
        status_callback_url: str,
    ) -> VoiceCallResult:
        raise NotImplementedError
