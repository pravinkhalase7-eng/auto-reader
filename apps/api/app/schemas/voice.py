from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PhoneCallOut(BaseModel):
    id: str
    reminder_id: Optional[str] = None
    appointment_id: Optional[str] = None
    twilio_call_sid: Optional[str] = None
    phone_number_masked: str = ""
    status: str
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None
    attempt_number: int = 1
    provider: str = "mock"
    created_at: datetime

    model_config = {"from_attributes": True}
