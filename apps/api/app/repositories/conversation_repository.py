from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, UserPreference


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, conversation_id: str, user_id: str) -> Conversation | None:
        return await self.db.scalar(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )

    async def list_for_user(self, user_id: str, limit: int = 30) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return list((await self.db.scalars(stmt)).all())

    async def messages(self, conversation_id: str, limit: int = 40) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = list((await self.db.scalars(stmt)).all())
        rows.reverse()
        return rows

    async def add_conversation(self, conversation: Conversation) -> Conversation:
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def add_message(self, message: Message) -> Message:
        self.db.add(message)
        await self.db.flush()
        return message


class PreferenceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: str) -> UserPreference | None:
        return await self.db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))

    async def get_or_create(self, user_id: str, timezone: str, language: str = "en") -> UserPreference:
        existing = await self.get(user_id)
        if existing:
            return existing
        pref = UserPreference(user_id=user_id, timezone=timezone, preferred_language=language)
        self.db.add(pref)
        await self.db.flush()
        return pref
