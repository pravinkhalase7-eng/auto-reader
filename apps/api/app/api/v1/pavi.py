from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.pavi_agent import PaviAgent
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models import User
from app.schemas.pavi import (
    ChatConfirmation,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationOut,
    MessageOut,
    PreferenceIn,
    PreferenceOut,
    PaviStatsOut,
    UpcomingScheduleOut,
    VoiceTranscriptRequest,
)
from app.services.pavi_service import ConversationService, pavi_stats, upcoming_schedule
from app.services.preference_service import PreferenceService, preference_to_out

router = APIRouter(prefix="/pavi", tags=["pavi"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return await _handle_chat(body.message, body.conversation_id, user, db, body.idempotency_key or idempotency_key)


@router.post("/voice/transcript", response_model=ChatResponse)
async def voice_transcript(
    body: VoiceTranscriptRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    text = (body.transcript or body.message or "").strip()
    return await _handle_chat(text, body.conversation_id, user, db, body.idempotency_key, message_type="voice")


async def _handle_chat(
    message: str,
    conversation_id: str | None,
    user: User,
    db: AsyncSession,
    idempotency_key: str | None = None,
    message_type: str = "text",
) -> ChatResponse:
    conv_svc = ConversationService(db, user)
    conversation = await conv_svc.ensure(conversation_id, message)
    history = await conv_svc.history(conversation.id)
    await conv_svc.add_message(conversation, "user", message, message_type=message_type)
    agent = PaviAgent(db, user)
    result = await agent.reply(message, history)
    await conv_svc.add_message(conversation, "assistant", result.text)
    confirmation = None
    if result.confirmation:
        confirmation = ChatConfirmation(
            kind=result.confirmation["kind"],
            title=result.confirmation["title"],
            when_label=result.confirmation.get("when_label") or "",
            phone_call_enabled=bool(result.confirmation.get("phone_call_enabled")),
            extra=result.confirmation.get("extra"),
        )
    return ChatResponse(conversation_id=conversation.id, message=result.text, confirmation=confirmation)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await ConversationService(db, user).list()
    return [ConversationOut.model_validate(r) for r in rows]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ConversationService(db, user)
    row = await svc.get(conversation_id)
    if not row:
        raise NotFoundError("I couldn't find that conversation.")
    messages = await svc.detail_messages(conversation_id)
    return ConversationDetail(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.get("/preferences", response_model=PreferenceOut)
async def get_preferences(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pref = await PreferenceService(db, user).get()
    return preference_to_out(pref)


@router.patch("/preferences", response_model=PreferenceOut)
async def update_preferences(
    body: PreferenceIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pref = await PreferenceService(db, user).update(body)
    return preference_to_out(pref)


@router.get("/schedule", response_model=UpcomingScheduleOut)
async def get_schedule(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await upcoming_schedule(db, user)


@router.get("/stats", response_model=PaviStatsOut)
async def get_stats(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return PaviStatsOut(**await pavi_stats(db, user))
