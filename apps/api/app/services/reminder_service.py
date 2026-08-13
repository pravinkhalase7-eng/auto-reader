from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.models import Reminder, User
from app.repositories.conversation_repository import PreferenceRepository
from app.repositories.reminder_repository import ReminderRepository, operation_key
from app.schemas.reminder import ReminderCreate, ReminderOut, ReminderUpdate
from app.utils.datetime import format_local, now_utc, parse_iso_or_natural
from app.utils.phone import mask_phone, validate_phone

ACTIVE = {"pending", "scheduled"}


def to_out(reminder: Reminder) -> ReminderOut:
    return ReminderOut(
        id=reminder.id,
        title=reminder.title,
        description=reminder.description,
        reminder_time_utc=reminder.reminder_time_utc,
        when_label=format_local(reminder.reminder_time_utc, reminder.timezone),
        timezone=reminder.timezone,
        status=reminder.status,
        reminder_type=reminder.reminder_type,
        phone_call_enabled=reminder.phone_call_enabled,
        phone_number_masked=mask_phone(reminder.phone_number),
        recurrence_rule=reminder.recurrence_rule,
        language=reminder.language,
        appointment_id=reminder.appointment_id,
        booking_id=reminder.booking_id,
        last_error=reminder.last_error or reminder.call_scheduling_error,
        created_at=reminder.created_at,
        updated_at=reminder.updated_at,
        completed_at=reminder.completed_at,
        cancelled_at=reminder.cancelled_at,
    )


class ReminderService:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self.repo = ReminderRepository(db)
        self.prefs = PreferenceRepository(db)
        self.settings = get_settings()

    async def _prefs(self):
        return await self.prefs.get_or_create(
            self.user.id,
            timezone=self.settings.default_timezone,
            language=self.user.ui_language or "en",
        )

    async def create(self, body: ReminderCreate) -> Reminder:
        pref = await self._prefs()
        tz = body.timezone or pref.timezone or self.settings.default_timezone
        parsed = parse_iso_or_natural(body.reminder_time, timezone_name=tz)
        if not parsed:
            raise AppError(
                "I couldn't understand that time. Could you include a date and time, like tomorrow at 12 PM?",
                code="UNCLEAR_TIME",
            )
        key = body.idempotency_key or operation_key(
            self.user.id, body.title, parsed.dt_utc.replace(second=0, microsecond=0).isoformat()
        )
        existing = await self.repo.get_by_idempotency(self.user.id, key)
        if existing:
            return existing

        phone = None
        if body.phone_number:
            phone = validate_phone(body.phone_number)
        elif body.phone_call_enabled:
            phone = pref.phone_number

        reminder_type = body.reminder_type
        if body.phone_call_enabled and reminder_type == "notification":
            reminder_type = "both"

        reminder = Reminder(
            user_id=self.user.id,
            title=body.title.strip(),
            description=body.description,
            reminder_time_utc=parsed.dt_utc,
            timezone=tz,
            status="scheduled",
            reminder_type=reminder_type,
            phone_call_enabled=body.phone_call_enabled,
            phone_number=phone,
            recurrence_rule=body.recurrence_rule or parsed.recurrence_rule,
            language=body.language or pref.preferred_language,
            appointment_id=body.appointment_id,
            booking_id=body.booking_id,
            idempotency_key=key,
        )
        if body.phone_call_enabled and not phone:
            reminder.call_scheduling_error = "No phone number on file"
        await self.repo.add(reminder)
        await self.db.commit()
        await self.db.refresh(reminder)
        return reminder

    async def list(
        self,
        *,
        upcoming_only: bool = False,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Reminder]:
        return await self.repo.list_for_user(
            self.user.id, upcoming_only=upcoming_only, start=start, end=end
        )

    async def get(self, reminder_id: str) -> Reminder:
        reminder = await self.repo.get(reminder_id, self.user.id)
        if not reminder:
            raise NotFoundError("I couldn't find that reminder.")
        return reminder

    async def update(self, reminder_id: str, body: ReminderUpdate) -> Reminder:
        reminder = await self.get(reminder_id)
        pref = await self._prefs()
        tz = body.timezone or reminder.timezone
        if body.title is not None:
            reminder.title = body.title.strip()
        if body.description is not None:
            reminder.description = body.description
        if body.reminder_time:
            parsed = parse_iso_or_natural(body.reminder_time, timezone_name=tz)
            if not parsed:
                raise AppError("I couldn't understand the new time.", code="UNCLEAR_TIME")
            reminder.reminder_time_utc = parsed.dt_utc
            reminder.timezone = tz
            if reminder.status in {"completed", "failed", "processing"}:
                reminder.status = "scheduled"
                reminder.completed_at = None
        if body.phone_call_enabled is not None:
            reminder.phone_call_enabled = body.phone_call_enabled
        if body.phone_number:
            reminder.phone_number = validate_phone(body.phone_number)
        if body.language:
            reminder.language = body.language
        if body.recurrence_rule is not None:
            reminder.recurrence_rule = body.recurrence_rule
        if body.reminder_type:
            reminder.reminder_type = body.reminder_type
        if reminder.phone_call_enabled and not reminder.phone_number:
            reminder.phone_number = pref.phone_number
        await self.db.commit()
        await self.db.refresh(reminder)
        return reminder

    async def cancel(self, reminder_id: str) -> Reminder:
        reminder = await self.get(reminder_id)
        reminder.status = "cancelled"
        reminder.cancelled_at = now_utc()
        if reminder.appointment_id:
            from app.models import Appointment

            appt = await self.db.get(Appointment, reminder.appointment_id)
            if appt and appt.user_id == self.user.id and appt.status != "cancelled":
                appt.status = "cancelled"
                appt.cancelled_at = now_utc()
        if reminder.booking_id:
            from app.models import Booking

            booking = await self.db.get(Booking, reminder.booking_id)
            if booking and booking.user_id == self.user.id and booking.status != "cancelled":
                booking.status = "cancelled"
                booking.cancelled_at = now_utc()
        await self.db.commit()
        await self.db.refresh(reminder)
        return reminder

    async def cancel_linked(self, *, appointment_id: str | None = None, booking_id: str | None = None) -> int:
        return await self.repo.cancel_active_linked(
            self.user.id, appointment_id=appointment_id, booking_id=booking_id
        )

    async def set_phone_call(self, reminder_id: str, enabled: bool, phone_number: str | None = None) -> Reminder:
        reminder = await self.get(reminder_id)
        reminder.phone_call_enabled = enabled
        if phone_number:
            reminder.phone_number = validate_phone(phone_number)
        if enabled and not reminder.phone_number:
            pref = await self._prefs()
            reminder.phone_number = pref.phone_number
        if enabled:
            reminder.reminder_type = "both" if reminder.reminder_type == "notification" else reminder.reminder_type
        else:
            reminder.reminder_type = "notification"
        await self.db.commit()
        await self.db.refresh(reminder)
        return reminder

    async def latest_active(self) -> Reminder | None:
        rows = await self.repo.list_for_user(self.user.id, upcoming_only=True, limit=1)
        if rows:
            return rows[0]
        all_rows = await self.repo.list_for_user(self.user.id, include_cancelled=False, limit=1)
        return all_rows[0] if all_rows else None
