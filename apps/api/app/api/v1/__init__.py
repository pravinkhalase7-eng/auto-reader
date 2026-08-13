from fastapi import APIRouter

from app.api.v1 import appointments, auth, dashboard, lessons, pavi, quizzes, reminders, storage, tts, voice

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
    return {"status": "ok", "service": "ai-teacher"}
