from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.sync_database import SyncSessionLocal
from app.models import Appointment, PhoneCall, Reminder, UserPreference
from app.repositories.reminder_repository import SyncReminderRepository
from app.services.reminder_message import generate_reminder_speech
from app.services.tts_service import TTSService
from app.services.twilio_service import TwilioVoiceService
from app.utils.datetime import next_recurrence, now_utc
from app.utils.phone import mask_phone
from app.workers.celery_app import celery_app

logger = logging.getLogger("app.pavi.worker")


@celery_app.task(name="app.workers.reminder_tasks.process_reminder", bind=True, max_retries=0)
def process_reminder(self, reminder_id: str) -> str:
    return process_reminder_now(reminder_id)


def process_reminder_now(reminder_id: str) -> str:
    session = SyncSessionLocal()
    try:
        return _process(session, reminder_id)
    finally:
        session.close()


def _process(session: Session, reminder_id: str) -> str:
    settings = get_settings()
    reminder = session.get(Reminder, reminder_id)
    if not reminder:
        logger.warning("[REMINDER] id=%s status=missing", reminder_id)
        return "missing"
    if reminder.status not in {"processing", "scheduled"}:
        logger.info("[REMINDER] id=%s status=%s skipped", reminder_id, reminder.status)
        return reminder.status
    if reminder.status == "scheduled":
        reminder.status = "processing"
        session.commit()

    logger.info("[REMINDER] id=%s status=processing", reminder.id)
    appointment = session.get(Appointment, reminder.appointment_id) if reminder.appointment_id else None
    pref = session.scalar(select(UserPreference).where(UserPreference.user_id == reminder.user_id))
    language = reminder.language or (pref.preferred_language if pref else "en")
    spoken = generate_reminder_speech(reminder, appointment=appointment, language=language)

    audio_key = None
    try:
        import asyncio

        audio, audio_key = asyncio.run(TTSService().synthesize_to_file(spoken, language=language))
        provider_name = audio.provider
    except Exception as exc:  # noqa: BLE001
        logger.exception("[TTS] reminder_id=%s failed", reminder.id)
        provider_name = "none"
        reminder.call_scheduling_error = f"TTS failed: {exc}"

    phone = reminder.phone_number or (pref.phone_number if pref else None)
    wants_call = reminder.phone_call_enabled and reminder.reminder_type in {"phone_call", "both"}
    if wants_call and not phone:
        reminder.call_scheduling_error = "No phone number on file"
        reminder.status = "completed" if not reminder.phone_call_enabled else "failed"
        reminder.last_error = reminder.call_scheduling_error
        reminder.completed_at = now_utc()
        session.commit()
        logger.info("[REMINDER] id=%s status=%s reason=no_phone", reminder.id, reminder.status)
        return reminder.status

    if not wants_call:
        _complete_or_recur(session, reminder)
        logger.info("[REMINDER] id=%s status=completed kind=notification", reminder.id)
        return "completed"

    existing = session.scalar(
        select(PhoneCall)
        .where(PhoneCall.reminder_id == reminder.id, PhoneCall.status.in_(["queued", "ringing", "in-progress", "completed"]))
        .order_by(PhoneCall.created_at.desc())
    )
    if existing and existing.status == "completed":
        reminder.status = "completed"
        reminder.completed_at = now_utc()
        session.commit()
        return "completed"

    call = PhoneCall(
        user_id=reminder.user_id,
        reminder_id=reminder.id,
        appointment_id=reminder.appointment_id,
        phone_number=phone,
        status="queued",
        spoken_text=spoken,
        audio_key=audio_key,
        attempt_number=(reminder.retry_count or 0) + 1,
        provider="mock" if settings.voice_call_mode == "mock" else "twilio",
    )
    session.add(call)
    session.flush()
    try:
        result = TwilioVoiceService().make_call(to=phone, reminder_id=reminder.id)
        call.twilio_call_sid = result.call_sid
        call.status = result.status
        call.provider = result.provider
        call.started_at = now_utc()
        if result.provider == "mock" and result.status == "completed":
            call.completed_at = now_utc()
            call.answered_at = now_utc()
            call.duration_seconds = 8
            _complete_or_recur(session, reminder)
        session.commit()
        logger.info(
            "[VOICE_CALL] reminder_id=%s twilio_sid=%s status=%s to=%s",
            reminder.id,
            result.call_sid,
            result.status,
            mask_phone(phone),
        )
        return call.status
    except Exception as exc:  # noqa: BLE001
        logger.exception("[VOICE_CALL] reminder_id=%s status=failed", reminder.id)
        call.status = "failed"
        call.error_message = str(exc)
        reminder.call_scheduling_error = "The reminder was saved, but I couldn't schedule the phone call."
        _schedule_retry_or_fail(session, reminder, str(exc))
        session.commit()
        return "failed"


def _complete_or_recur(session: Session, reminder: Reminder) -> None:
    if reminder.recurrence_rule:
        reminder.reminder_time_utc = next_recurrence(reminder.reminder_time_utc, reminder.recurrence_rule)
        reminder.status = "scheduled"
        reminder.retry_count = 0
        reminder.last_error = None
    else:
        reminder.status = "completed"
        reminder.completed_at = now_utc()


def _schedule_retry_or_fail(session: Session, reminder: Reminder, error: str) -> None:
    settings = get_settings()
    reminder.retry_count = (reminder.retry_count or 0) + 1
    reminder.last_error = error
    delays = settings.retry_delay_list
    if reminder.retry_count <= settings.call_max_retries:
        delay_idx = min(reminder.retry_count - 1, len(delays) - 1)
        reminder.status = "scheduled"
        reminder.reminder_time_utc = now_utc() + timedelta(seconds=delays[delay_idx])
        reminder.next_retry_at = reminder.reminder_time_utc
        logger.info("[REMINDER] id=%s status=scheduled retry=%s", reminder.id, reminder.retry_count)
    else:
        reminder.status = "failed"
        logger.info("[REMINDER] id=%s status=failed retries_exhausted", reminder.id)
