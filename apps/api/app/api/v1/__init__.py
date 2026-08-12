from fastapi import APIRouter

from app.api.v1 import auth, dashboard, lessons, quizzes, storage

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(lessons.router)
api_router.include_router(quizzes.router)
api_router.include_router(dashboard.router)
api_router.include_router(storage.router)


@api_router.get("/health")
async def health():
    return {"status": "ok", "service": "ai-teacher"}
