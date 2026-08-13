from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, max_length=128)


class VoiceTranscriptRequest(ChatRequest):
    transcript: Optional[str] = None


class ChatConfirmation(BaseModel):
    kind: str
    title: str
    when_label: str
    phone_call_enabled: bool = False
    extra: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    role: str = "assistant"
    confirmation: Optional[ChatConfirmation] = None
    reminders: list[dict[str, Any]] = []
    appointments: list[dict[str, Any]] = []


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    message_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


class PreferenceIn(BaseModel):
    phone_number: Optional[str] = None
    phone_call_enabled: Optional[bool] = None
    preferred_language: Optional[str] = Field(default=None, pattern="^(en|hi|mr)$")
    timezone: Optional[str] = None


class PreferenceOut(BaseModel):
    phone_number: Optional[str] = None
    phone_number_masked: str = ""
    phone_call_enabled: bool = True
    preferred_language: str = "en"
    timezone: str = "Asia/Kolkata"

    model_config = {"from_attributes": True}


class PaviStatsOut(BaseModel):
    total_reminders: int = 0
    pending_reminders: int = 0
    completed_reminders: int = 0
    failed_reminders: int = 0
    calls_made: int = 0
    calls_answered: int = 0
    calls_failed: int = 0


class ScheduleItem(BaseModel):
    id: str
    kind: str
    title: str
    when_utc: datetime
    when_label: str
    timezone: str
    phone_call_enabled: bool = False
    status: str
    location: Optional[str] = None


class UpcomingScheduleOut(BaseModel):
    timezone: str
    items: list[ScheduleItem]
    today: list[ScheduleItem]
    tomorrow: list[ScheduleItem]
    later: list[ScheduleItem]


class TestCallRequest(BaseModel):
    phone_number: str
    message: str = "Hello, this is a test call from Pavi."
