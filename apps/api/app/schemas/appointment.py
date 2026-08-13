from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    appointment_time: str = Field(min_length=1)
    timezone: Optional[str] = None
    location: Optional[str] = None
    booking_reference: Optional[str] = None
    phone_call_enabled: bool = True
    language: Optional[str] = None
    reminder_offset_minutes: Optional[int] = Field(default=None, ge=0, le=7 * 24 * 60)
    idempotency_key: Optional[str] = None


class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    appointment_time: Optional[str] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    booking_reference: Optional[str] = None
    phone_call_enabled: Optional[bool] = None
    status: Optional[str] = None


class AppointmentOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    appointment_time_utc: datetime
    when_label: str = ""
    timezone: str
    location: Optional[str] = None
    booking_reference: Optional[str] = None
    phone_call_enabled: bool
    status: str
    language: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    booking_time: str = Field(min_length=1)
    timezone: Optional[str] = None
    location: Optional[str] = None
    booking_reference: Optional[str] = None
    booking_type: str = "other"
    phone_call_enabled: bool = True
    reminder_offset_minutes: Optional[int] = Field(default=None, ge=0, le=7 * 24 * 60)


class BookingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    booking_time: Optional[str] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    booking_reference: Optional[str] = None
    phone_call_enabled: Optional[bool] = None
    status: Optional[str] = None


class BookingOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    booking_time_utc: datetime
    when_label: str = ""
    timezone: str
    location: Optional[str] = None
    booking_reference: Optional[str] = None
    booking_type: str
    phone_call_enabled: bool
    status: str
    language: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
