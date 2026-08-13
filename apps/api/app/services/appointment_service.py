from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.models import Appointment, Booking, User
from app.repositories.appointment_repository import AppointmentRepository, BookingRepository
from app.repositories.conversation_repository import PreferenceRepository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, BookingCreate, BookingUpdate
from app.schemas.reminder import ReminderCreate
from app.services.reminder_service import ReminderService, to_out as reminder_to_out
from app.utils.datetime import format_local, now_utc, parse_iso_or_natural
from app.utils.phone import mask_phone


def appointment_to_out(row: Appointment):
    from app.schemas.appointment import AppointmentOut

    return AppointmentOut(
        id=row.id,
        title=row.title,
        description=row.description,
        appointment_time_utc=row.appointment_time_utc,
        when_label=format_local(row.appointment_time_utc, row.timezone),
        timezone=row.timezone,
        location=row.location,
        booking_reference=row.booking_reference,
        phone_call_enabled=row.phone_call_enabled,
        status=row.status,
        language=row.language,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def booking_to_out(row: Booking):
    from app.schemas.appointment import BookingOut

    return BookingOut(
        id=row.id,
        title=row.title,
        description=row.description,
        booking_time_utc=row.booking_time_utc,
        when_label=format_local(row.booking_time_utc, row.timezone),
        timezone=row.timezone,
        location=row.location,
        booking_reference=row.booking_reference,
        booking_type=row.booking_type,
        phone_call_enabled=row.phone_call_enabled,
        status=row.status,
        language=row.language,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class AppointmentService:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self.repo = AppointmentRepository(db)
        self.prefs = PreferenceRepository(db)
        self.settings = get_settings()

    async def create(self, body: AppointmentCreate) -> tuple[Appointment, object | None]:
        pref = await self.prefs.get_or_create(self.user.id, self.settings.default_timezone, self.user.ui_language or "en")
        tz = body.timezone or pref.timezone
        parsed = parse_iso_or_natural(body.appointment_time, timezone_name=tz)
        if not parsed:
            raise AppError("I couldn't understand the appointment time.", code="UNCLEAR_TIME")
        row = Appointment(
            user_id=self.user.id,
            title=body.title.strip(),
            description=body.description,
            appointment_time_utc=parsed.dt_utc,
            timezone=tz,
            location=body.location,
            booking_reference=body.booking_reference,
            phone_call_enabled=body.phone_call_enabled,
            status="scheduled",
            language=body.language or pref.preferred_language,
        )
        await self.repo.add(row)
        await self.db.flush()
        reminder = None
        offset = body.reminder_offset_minutes if body.reminder_offset_minutes is not None else 0
        remind_at = parsed.dt_utc - timedelta(minutes=offset)
        reminder = await ReminderService(self.db, self.user).create(
            ReminderCreate(
                title=body.title.strip(),
                description=body.description or (f"At {body.location}" if body.location else None),
                reminder_time=remind_at.isoformat(),
                timezone=tz,
                phone_call_enabled=body.phone_call_enabled,
                language=body.language or pref.preferred_language,
                appointment_id=row.id,
                idempotency_key=body.idempotency_key,
            )
        )
        await self.db.commit()
        await self.db.refresh(row)
        return row, reminder

    async def list(self, *, upcoming_only: bool = False):
        return await self.repo.list_for_user(self.user.id, upcoming_only=upcoming_only)

    async def get(self, appointment_id: str) -> Appointment:
        row = await self.repo.get(appointment_id, self.user.id)
        if not row:
            raise NotFoundError("I couldn't find that appointment.")
        return row

    async def update(self, appointment_id: str, body: AppointmentUpdate) -> Appointment:
        row = await self.get(appointment_id)
        tz = body.timezone or row.timezone
        if body.title is not None:
            row.title = body.title.strip()
        if body.description is not None:
            row.description = body.description
        if body.appointment_time:
            parsed = parse_iso_or_natural(body.appointment_time, timezone_name=tz)
            if not parsed:
                raise AppError("I couldn't understand the new appointment time.", code="UNCLEAR_TIME")
            row.appointment_time_utc = parsed.dt_utc
            row.timezone = tz
        if body.location is not None:
            row.location = body.location
        if body.booking_reference is not None:
            row.booking_reference = body.booking_reference
        if body.phone_call_enabled is not None:
            row.phone_call_enabled = body.phone_call_enabled
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def cancel(self, appointment_id: str = "") -> Appointment:
        if not appointment_id:
            rows = await self.list(upcoming_only=True) or await self.list()
            if not rows:
                raise NotFoundError("I couldn't find that appointment.")
            appointment_id = rows[0].id
        row = await self.get(appointment_id)
        row.status = "cancelled"
        row.cancelled_at = now_utc()
        await ReminderService(self.db, self.user).cancel_linked(appointment_id=row.id)
        await self.db.commit()
        await self.db.refresh(row)
        return row


class BookingService:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self.repo = BookingRepository(db)
        self.prefs = PreferenceRepository(db)
        self.settings = get_settings()

    async def create(self, body: BookingCreate) -> tuple[Booking, object | None]:
        pref = await self.prefs.get_or_create(self.user.id, self.settings.default_timezone, self.user.ui_language or "en")
        tz = body.timezone or pref.timezone
        parsed = parse_iso_or_natural(body.booking_time, timezone_name=tz)
        if not parsed:
            raise AppError("I couldn't understand the booking time.", code="UNCLEAR_TIME")
        row = Booking(
            user_id=self.user.id,
            title=body.title.strip(),
            description=body.description,
            booking_time_utc=parsed.dt_utc,
            timezone=tz,
            location=body.location,
            booking_reference=body.booking_reference,
            booking_type=body.booking_type,
            phone_call_enabled=body.phone_call_enabled,
            status="scheduled",
            language=pref.preferred_language,
        )
        await self.repo.add(row)
        await self.db.flush()
        offset = body.reminder_offset_minutes or 0
        remind_at = parsed.dt_utc - timedelta(minutes=offset)
        reminder = await ReminderService(self.db, self.user).create(
            ReminderCreate(
                title=body.title.strip(),
                description=body.description,
                reminder_time=remind_at.isoformat(),
                timezone=tz,
                phone_call_enabled=body.phone_call_enabled,
                booking_id=row.id,
            )
        )
        await self.db.commit()
        await self.db.refresh(row)
        return row, reminder

    async def list(self, *, upcoming_only: bool = False):
        return await self.repo.list_for_user(self.user.id, upcoming_only=upcoming_only)

    async def get(self, booking_id: str) -> Booking:
        row = await self.repo.get(booking_id, self.user.id)
        if not row:
            raise NotFoundError("I couldn't find that booking.")
        return row

    async def update(self, booking_id: str, body: BookingUpdate) -> Booking:
        row = await self.get(booking_id)
        tz = body.timezone or row.timezone
        if body.title is not None:
            row.title = body.title.strip()
        if body.booking_time:
            parsed = parse_iso_or_natural(body.booking_time, timezone_name=tz)
            if not parsed:
                raise AppError("I couldn't understand the new booking time.", code="UNCLEAR_TIME")
            row.booking_time_utc = parsed.dt_utc
            row.timezone = tz
        if body.location is not None:
            row.location = body.location
        if body.status:
            row.status = body.status
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def cancel(self, booking_id: str = "") -> Booking:
        if not booking_id:
            rows = await self.list(upcoming_only=True) or await self.list()
            if not rows:
                raise NotFoundError("I couldn't find that booking.")
            booking_id = rows[0].id
        row = await self.get(booking_id)
        row.status = "cancelled"
        row.cancelled_at = now_utc()
        await ReminderService(self.db, self.user).cancel_linked(booking_id=row.id)
        await self.db.commit()
        await self.db.refresh(row)
        return row
