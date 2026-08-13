from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import AppError, to_http_exception
from app.models import User
from app.services.elevenlabs import elevenlabs_enabled, list_voices, synthesize

router = APIRouter(prefix="/tts", tags=["tts"])


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice_id: str = Field(min_length=1, max_length=80)
    speed: str = "normal"
    language: str = "en"


@router.get("/voices")
async def tts_voices(_: User = Depends(get_current_user)):
    enabled = elevenlabs_enabled()
    voices = await list_voices() if enabled else []
    if enabled and not voices:
        settings = get_settings()
        voices = [
            {
                "id": settings.elevenlabs_voice_id,
                "name": "ElevenLabs teacher",
                "accent": "",
                "category": "default",
            }
        ]
    return {"elevenlabs": enabled, "voices": voices}


@router.post("/speak")
async def tts_speak(body: SpeakRequest, _: User = Depends(get_current_user)):
    try:
        audio = await synthesize(body.text, body.voice_id, speed=body.speed, language=body.language)
    except AppError as exc:
        raise to_http_exception(exc) from exc
    return Response(content=audio, media_type="audio/mpeg")
