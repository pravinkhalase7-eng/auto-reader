from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    phone_call_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")


class Conversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="New conversation")


class Message(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system | tool
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(32), default="text")


class Reminder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reminders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_reminder_idempotency"),
        Index("ix_reminders_due", "status", "reminder_time_utc"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reminder_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    status: Mapped[str] = mapped_column(String(32), default="scheduled", index=True)
    reminder_type: Mapped[str] = mapped_column(String(32), default="both")
    phone_call_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    appointment_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    booking_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    call_scheduling_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Appointment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "appointments"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    appointment_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    booking_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    phone_call_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled", index=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Booking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "bookings"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    booking_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    booking_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    booking_type: Mapped[str] = mapped_column(String(64), default="other")
    phone_call_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled", index=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PhoneCall(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "phone_calls"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reminder_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    appointment_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )
    twilio_call_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    spoken_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    provider: Mapped[str] = mapped_column(String(32), default="mock")


class PaviIdempotencyKey(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pavi_idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_pavi_idempotency_user_key"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(36))
