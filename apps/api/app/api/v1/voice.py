from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.models import PhoneCall, Reminder, User
from app.repositories.phone_call_repository import PhoneCallRepository
from app.schemas.pavi import TestCallRequest
from app.schemas.voice import PhoneCallOut
from app.services.tts_service import TTSService
from app.services.twilio_service import TwilioVoiceService
from app.utils.datetime import now_utc
from app.utils.phone import mask_phone, validate_phone

logger = logging.getLogger("app.pavi.voice")
router = APIRouter(prefix="/voice", tags=["voice"])
dev_router = APIRouter(prefix="/dev", tags=["dev"])


def _call_out(row: PhoneCall) -> PhoneCallOut:
    return PhoneCallOut(
        id=row.id,
        reminder_id=row.reminder_id,
        appointment_id=row.appointment_id,
        twilio_call_sid=row.twilio_call_sid,
        phone_number_masked=mask_phone(row.phone_number),
        status=row.status,
        started_at=row.started_at,
        answered_at=row.answered_at,
        completed_at=row.completed_at,
        duration_seconds=row.duration_seconds,
        error_message=row.error_message,
        attempt_number=row.attempt_number,
        provider=row.provider,
        created_at=row.created_at,
    )


@router.get("/calls", response_model=list[PhoneCallOut])
async def list_calls(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await PhoneCallRepository(db).list_for_user(user.id)
    return [_call_out(r) for r in rows]


@router.get("/audio/{audio_key}")
async def get_audio(audio_key: str):
    path = TTSService().path_for(audio_key)
    if not path.exists():
        raise NotFoundError("Audio not found.")
    return FileResponse(path, media_type="audio/wav")


@router.post("/twilio/twiml/{reminder_id}")
async def twilio_twiml(reminder_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    form = dict((await request.form()).items())
    service = TwilioVoiceService()
    if not service.validate_request(request, {k: str(v) for k, v in form.items()}):
        return Response(status_code=403, content="Invalid signature")
    reminder = await db.get(Reminder, reminder_id)
    if not reminder:
        xml = service.generate_twiml(spoken_text="Hello, this is Pavi. Your reminder is no longer available.", audio_url=None)
        return Response(content=xml, media_type="application/xml")
    call = await db.scalar(
        select(PhoneCall).where(PhoneCall.reminder_id == reminder_id).order_by(PhoneCall.created_at.desc())
    )
    spoken = (call.spoken_text if call else None) or f"Hello, this is Pavi. This is your reminder: {reminder.title}."
    audio_url = None
    if call and call.audio_key:
        audio_url = service.audio_url(call.audio_key)
    xml = service.generate_twiml(spoken_text=spoken, audio_url=audio_url, language=reminder.language)
    return Response(content=xml, media_type="application/xml")


@router.post("/twilio/status")
async def twilio_status(request: Request, db: AsyncSession = Depends(get_db)):
    form = {k: str(v) for k, v in dict((await request.form()).items()).items()}
    service = TwilioVoiceService()
    if not service.validate_request(request, form):
        return Response(status_code=403, content="Invalid signature")
    sid = form.get("CallSid") or form.get("call_sid")
    status = (form.get("CallStatus") or form.get("call_status") or "").lower()
    duration = form.get("CallDuration") or form.get("call_duration")
    call = await PhoneCallRepository(db).get_by_sid(sid) if sid else None
    if not call:
        logger.info("[VOICE_CALL] twilio_sid=%s status=%s unmatched", sid, status)
        return {"ok": True}
    call.status = status or call.status
    if status in {"in-progress", "answered"} and not call.answered_at:
        call.answered_at = now_utc()
    if status in {"completed", "busy", "failed", "no-answer", "canceled", "cancelled"}:
        call.completed_at = now_utc()
        if duration and duration.isdigit():
            call.duration_seconds = int(duration)
        reminder = await db.get(Reminder, call.reminder_id) if call.reminder_id else None
        if reminder and reminder.status == "processing":
            if status == "completed":
                reminder.status = "completed"
                reminder.completed_at = now_utc()
            elif status in {"busy", "failed", "no-answer", "canceled", "cancelled"}:
                from app.workers.reminder_tasks import _schedule_retry_or_fail

                # Keep reminder failed/retry via a lightweight inline update (async).
                settings = get_settings()
                reminder.retry_count = (reminder.retry_count or 0) + 1
                reminder.last_error = status
                if reminder.retry_count <= settings.call_max_retries:
                    from datetime import timedelta

                    delays = settings.retry_delay_list
                    delay_idx = min(reminder.retry_count - 1, len(delays) - 1)
                    reminder.status = "scheduled"
                    reminder.reminder_time_utc = now_utc() + timedelta(seconds=delays[delay_idx])
                else:
                    reminder.status = "failed"
    await db.commit()
    logger.info("[VOICE_CALL] reminder_id=%s twilio_sid=%s status=%s", call.reminder_id, sid, status)
    return {"ok": True}


@dev_router.post("/test-call")
async def test_call(
    body: TestCallRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not settings.dev_tools_enabled:
        raise AppError("Test calls are disabled.", code="DEV_TOOLS_DISABLED", status_code=403)
    phone = validate_phone(body.phone_number)
    from app.models import Reminder
    from app.utils.datetime import now_utc as utcnow

    reminder = Reminder(
        user_id=user.id,
        title="Pavi test call",
        description=body.message,
        reminder_time_utc=utcnow(),
        timezone=settings.default_timezone,
        status="processing",
        reminder_type="phone_call",
        phone_call_enabled=True,
        phone_number=phone,
        language="en",
    )
    db.add(reminder)
    await db.flush()
    tts = TTSService()
    audio, key = await tts.synthesize_to_file(body.message, language="en")
    call = PhoneCall(
        user_id=user.id,
        reminder_id=reminder.id,
        phone_number=phone,
        status="queued",
        spoken_text=body.message,
        audio_key=key,
        provider="mock" if settings.voice_call_mode == "mock" else "twilio",
    )
    db.add(call)
    await db.flush()
    result = TwilioVoiceService().make_call(to=phone, reminder_id=reminder.id)
    call.twilio_call_sid = result.call_sid
    call.status = result.status
    call.provider = result.provider
    await db.commit()
    logger.info("[VOICE_CALL] reminder_id=%s status=initiated test=true to=%s", reminder.id, mask_phone(phone))
    return {
        "ok": True,
        "mode": settings.voice_call_mode,
        "call_sid": result.call_sid,
        "status": result.status,
        "to": mask_phone(phone),
        "tts_provider": audio.provider,
    }
