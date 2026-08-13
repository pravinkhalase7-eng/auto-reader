from fastapi import APIRouter

from app.api.v1 import appointments, auth, dashboard, lessons, pavi, quizzes, reminders, storage, tts, voice
from app.core.config import get_settings

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(lessons.router)
api_router.include_router(quizzes.router)
api_router.include_router(dashboard.router)
api_router.include_router(storage.router)
api_router.include_router(tts.router)
api_router.include_router(pavi.router)
api_router.include_router(reminders.router)
api_router.include_router(appointments.router)
api_router.include_router(appointments.bookings_router)
api_router.include_router(voice.router)
api_router.include_router(voice.dev_router)


@api_router.get("/health")
async def health():
    s = get_settings()
    webhook = s.resolved_twilio_webhook_base
    local = "localhost" in webhook or "127.0.0.1" in webhook
    return {
        "status": "ok",
        "service": "ai-teacher",
        "voice_call_mode": s.voice_call_mode,
        "twilio_configured": bool(s.twilio_account_sid and s.twilio_auth_token and s.twilio_phone_number),
        "webhook_base": webhook,
        "webhook_public": not local,
    }
