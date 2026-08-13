from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    reminder_time: str = Field(min_length=1, description="ISO datetime or natural language")
    timezone: Optional[str] = None
    phone_call_enabled: bool = True
    phone_number: Optional[str] = None
    language: Optional[str] = None
    recurrence_rule: Optional[str] = None
    reminder_type: str = "both"
    appointment_id: Optional[str] = None
    booking_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    reminder_time: Optional[str] = None
    timezone: Optional[str] = None
    phone_call_enabled: Optional[bool] = None
    phone_number: Optional[str] = None
    language: Optional[str] = None
    recurrence_rule: Optional[str] = None
    reminder_type: Optional[str] = None
    status: Optional[str] = None


class ReminderOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    reminder_time_utc: datetime
    when_label: str = ""
    timezone: str
    status: str
    reminder_type: str
    phone_call_enabled: bool
    phone_number_masked: str = ""
    recurrence_rule: Optional[str] = None
    language: str
    appointment_id: Optional[str] = None
    booking_id: Optional[str] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
