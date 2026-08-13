"""ADK tools are thin wrappers around Pavi services. No SQLAlchemy here."""

from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.pavi import PreferenceIn
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, BookingCreate, BookingUpdate
from app.schemas.reminder import ReminderCreate, ReminderUpdate
from app.services.appointment_service import AppointmentService, appointment_to_out, booking_to_out
from app.services.preference_service import PreferenceService, preference_to_out
from app.services.reminder_service import ReminderService, to_out
from app.utils.datetime import format_local, now_utc, parse_iso_or_natural
from app.utils.phone import mask_phone

pavi_db: ContextVar[AsyncSession] = ContextVar("pavi_db")
pavi_user: ContextVar[User] = ContextVar("pavi_user")


def _svc_reminder() -> ReminderService:
    return ReminderService(pavi_db.get(), pavi_user.get())


def _svc_appt() -> AppointmentService:
    return AppointmentService(pavi_db.get(), pavi_user.get())


def _ok(payload: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, **payload}


def _err(message: str, code: str = "ERROR") -> dict[str, Any]:
    return {"success": False, "error": message, "code": code}


async def create_reminder(
    title: str,
    reminder_time: str,
    description: str = "",
    phone_call_enabled: bool = True,
    recurrence_rule: str = "",
    reminder_type: str = "both",
) -> dict:
    """Create a reminder. reminder_time may be ISO-8601 or natural language in the user's timezone."""
    try:
        row = await _svc_reminder().create(
            ReminderCreate(
                title=title,
                description=description or None,
                reminder_time=reminder_time,
                phone_call_enabled=phone_call_enabled,
                recurrence_rule=recurrence_rule or None,
                reminder_type=reminder_type,
            )
        )
        out = to_out(row)
        return _ok(
            {
                "reminder_id": row.id,
                "title": out.title,
                "when": out.when_label,
                "status": out.status,
                "phone_call_enabled": bool(row.phone_call_enabled),
                "needs_phone": bool(row.phone_call_enabled and not row.phone_number),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def get_reminders(day: str = "") -> dict:
    """List the user's reminders. Pass day as ISO date or natural language like 'tomorrow' to filter."""
    try:
        rows = await _svc_reminder().list()
        user = pavi_user.get()
        pref = await PreferenceService(pavi_db.get(), user).get()
        if day:
            from app.utils.datetime import get_zone, to_utc

            parsed = parse_iso_or_natural(day, timezone_name=pref.timezone)
            if parsed:
                zone = get_zone(pref.timezone)
                start_local = parsed.local_dt.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
                start_utc = to_utc(start_local)
                end_utc = start_utc + timedelta(days=1)
                rows = [r for r in rows if start_utc <= r.reminder_time_utc < end_utc]
        items = [{"id": r.id, "title": r.title, "when": to_out(r).when_label, "status": r.status} for r in rows]
        return _ok({"reminders": items, "count": len(items)})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc))


async def get_upcoming_reminders() -> dict:
    """List upcoming scheduled reminders."""
    try:
        rows = await _svc_reminder().list(upcoming_only=True)
        items = [{"id": r.id, "title": r.title, "when": to_out(r).when_label, "status": r.status} for r in rows]
        return _ok({"reminders": items, "count": len(items)})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc))


async def update_reminder(reminder_id: str = "", reminder_time: str = "", title: str = "") -> dict:
    """Update a reminder. If reminder_id is empty, update the most recent upcoming reminder."""
    try:
        svc = _svc_reminder()
        if not reminder_id:
            latest = await svc.latest_active()
            if not latest:
                return _err("I couldn't find a reminder to update.", "NOT_FOUND")
            reminder_id = latest.id
        row = await svc.update(
            reminder_id,
            ReminderUpdate(title=title or None, reminder_time=reminder_time or None),
        )
        out = to_out(row)
        return _ok({"reminder_id": row.id, "title": out.title, "when": out.when_label})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def cancel_reminder(reminder_id: str = "") -> dict:
    """Cancel a reminder. If reminder_id is empty, cancel the most recently discussed reminder."""
    try:
        svc = _svc_reminder()
        if not reminder_id:
            latest = await svc.latest_active()
            if not latest:
                return _err("I couldn't find a reminder to cancel.", "NOT_FOUND")
            reminder_id = latest.id
        row = await svc.cancel(reminder_id)
        return _ok({"reminder_id": row.id, "status": row.status, "title": row.title})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def create_appointment(
    title: str,
    appointment_time: str,
    location: str = "",
    reminder_offset_minutes: int = 0,
    phone_call_enabled: bool = True,
    description: str = "",
) -> dict:
    """Create an appointment in the user's IST timezone and schedule a phone call.

    By default the call happens at the appointment time (reminder_offset_minutes=0).
    Use reminder_offset_minutes=60 only when the user asks to be called earlier.
    """
    try:
        from app.services.appointment_service import AppointmentService

        row, reminder = await AppointmentService(pavi_db.get(), pavi_user.get()).create(
            AppointmentCreate(
                title=title,
                appointment_time=appointment_time,
                location=location or None,
                description=description or None,
                reminder_offset_minutes=reminder_offset_minutes or 0,
                phone_call_enabled=phone_call_enabled,
            )
        )
        out = appointment_to_out(row)
        payload: dict[str, Any] = {
            "appointment_id": row.id,
            "title": out.title,
            "when": out.when_label,
            "location": out.location,
            "timezone": "IST",
            "phone_call_enabled": bool(row.phone_call_enabled),
            "needs_phone": bool(reminder is not None and reminder.phone_call_enabled and not reminder.phone_number),
        }
        if reminder is not None:
            r_out = to_out(reminder)  # type: ignore[arg-type]
            payload["reminder_id"] = reminder.id  # type: ignore[union-attr]
            payload["reminder_when"] = r_out.when_label
            payload["will_call_at"] = r_out.when_label
        return _ok(payload)
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def get_appointments() -> dict:
    """List the user's appointments."""
    try:
        rows = await _svc_appt().list()
        items = [{"id": r.id, "title": r.title, "when": appointment_to_out(r).when_label, "status": r.status} for r in rows]
        return _ok({"appointments": items, "count": len(items)})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc))


async def update_appointment(appointment_id: str, appointment_time: str = "", title: str = "", location: str = "") -> dict:
    """Update an appointment."""
    try:
        row = await _svc_appt().update(
            appointment_id,
            AppointmentUpdate(
                title=title or None,
                appointment_time=appointment_time or None,
                location=location or None,
            ),
        )
        out = appointment_to_out(row)
        return _ok({"appointment_id": row.id, "title": out.title, "when": out.when_label})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def cancel_appointment(appointment_id: str = "") -> dict:
    """Cancel an appointment and its linked phone reminder. Empty id cancels the latest one."""
    try:
        row = await _svc_appt().cancel(appointment_id)
        return _ok({"appointment_id": row.id, "status": row.status, "title": row.title})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def create_booking(
    title: str,
    booking_time: str,
    location: str = "",
    booking_reference: str = "",
    reminder_offset_minutes: int = 0,
    phone_call_enabled: bool = True,
) -> dict:
    """Create a booking (hotel, flight, etc.) and an optional reminder."""
    try:
        from app.services.appointment_service import BookingService

        row, reminder = await BookingService(pavi_db.get(), pavi_user.get()).create(
            BookingCreate(
                title=title,
                booking_time=booking_time,
                location=location or None,
                booking_reference=booking_reference or None,
                reminder_offset_minutes=reminder_offset_minutes or 0,
                phone_call_enabled=phone_call_enabled,
            )
        )
        out = booking_to_out(row)
        payload: dict[str, Any] = {"booking_id": row.id, "title": out.title, "when": out.when_label}
        if reminder is not None:
            payload["reminder_when"] = to_out(reminder).when_label  # type: ignore[arg-type]
        return _ok(payload)
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def get_bookings() -> dict:
    """List bookings."""
    try:
        from app.services.appointment_service import BookingService

        rows = await BookingService(pavi_db.get(), pavi_user.get()).list()
        items = [{"id": r.id, "title": r.title, "when": booking_to_out(r).when_label} for r in rows]
        return _ok({"bookings": items, "count": len(items)})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc))


async def update_booking(booking_id: str, booking_time: str = "", title: str = "") -> dict:
    """Update a booking."""
    try:
        from app.services.appointment_service import BookingService

        row = await BookingService(pavi_db.get(), pavi_user.get()).update(
            booking_id, BookingUpdate(title=title or None, booking_time=booking_time or None)
        )
        return _ok({"booking_id": row.id, "title": row.title, "when": booking_to_out(row).when_label})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def cancel_booking(booking_id: str = "") -> dict:
    """Cancel a booking and its linked phone reminder. Empty id cancels the latest one."""
    try:
        from app.services.appointment_service import BookingService

        row = await BookingService(pavi_db.get(), pavi_user.get()).cancel(booking_id)
        return _ok({"booking_id": row.id, "status": row.status, "title": row.title})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def get_current_datetime() -> dict:
    """Return the current date and time in the user's timezone."""
    pref = await PreferenceService(pavi_db.get(), pavi_user.get()).get()
    now = now_utc()
    return _ok(
        {
            "utc": now.isoformat(),
            "timezone": pref.timezone,
            "local": format_local(now, pref.timezone),
        }
    )


async def get_user_preferences() -> dict:
    """Return the current user's timezone, language, and whether phone calls are enabled."""
    pref = await PreferenceService(pavi_db.get(), pavi_user.get()).get()
    out = preference_to_out(pref)
    return _ok(
        {
            "timezone": out.timezone,
            "preferred_language": out.preferred_language,
            "phone_call_enabled": out.phone_call_enabled,
            "phone_number_masked": out.phone_number_masked,
        }
    )


async def set_user_phone(phone_number: str) -> dict:
    """Save the user's Indian mobile number for appointment and reminder calls."""
    try:
        pref = await PreferenceService(pavi_db.get(), pavi_user.get()).update(
            PreferenceIn(phone_number=phone_number, phone_call_enabled=True)
        )
        out = preference_to_out(pref)
        return _ok({"phone_number_masked": out.phone_number_masked, "phone_call_enabled": out.phone_call_enabled})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def set_reminder_phone_call(reminder_id: str = "", phone_number: str = "") -> dict:
    """Enable a phone-call reminder. Uses the user's saved number if phone_number is empty."""
    try:
        svc = _svc_reminder()
        if not reminder_id:
            latest = await svc.latest_active()
            if not latest:
                return _err("I couldn't find a reminder.", "NOT_FOUND")
            reminder_id = latest.id
        row = await svc.set_phone_call(reminder_id, True, phone_number or None)
        return _ok({"reminder_id": row.id, "phone_call_enabled": True, "phone_number_masked": mask_phone(row.phone_number)})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


async def cancel_reminder_phone_call(reminder_id: str = "") -> dict:
    """Disable the phone call for a reminder. The reminder itself stays scheduled."""
    try:
        svc = _svc_reminder()
        if not reminder_id:
            latest = await svc.latest_active()
            if not latest:
                return _err("I couldn't find a reminder.", "NOT_FOUND")
            reminder_id = latest.id
        row = await svc.set_phone_call(reminder_id, False)
        return _ok({"reminder_id": row.id, "phone_call_enabled": False})
    except Exception as exc:  # noqa: BLE001
        return _err(str(exc), getattr(exc, "code", "ERROR"))


PAVI_TOOLS = [
    create_reminder,
    get_reminders,
    get_upcoming_reminders,
    update_reminder,
    cancel_reminder,
    create_appointment,
    get_appointments,
    update_appointment,
    cancel_appointment,
    create_booking,
    get_bookings,
    update_booking,
    cancel_booking,
    get_current_datetime,
    get_user_preferences,
    set_user_phone,
    set_reminder_phone_call,
    cancel_reminder_phone_call,
]
