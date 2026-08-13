from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.exceptions import AppError, to_http_exception
from app.models import User
from app.services.elevenlabs import elevenlabs_enabled, list_voices
from app.services.lesson_tts import cloud_voices, speak_lesson

router = APIRouter(prefix="/tts", tags=["tts"])


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice_id: str = Field(min_length=1, max_length=80)
    speed: str = "normal"
    language: str = "en"


@router.get("/voices")
async def tts_voices(_: User = Depends(get_current_user)):
    voices = await list_voices() if elevenlabs_enabled() else []
    if voices:
        return {"elevenlabs": True, "voices": voices}
    return {"elevenlabs": False, "voices": cloud_voices()}


@router.post("/speak")
async def tts_speak(body: SpeakRequest, _: User = Depends(get_current_user)):
    try:
        audio, content_type = await speak_lesson(
            body.text,
            body.voice_id,
            speed=body.speed,
            language=body.language,
        )
    except AppError as exc:
        raise to_http_exception(exc) from exc
    return Response(content=audio, media_type=content_type)
