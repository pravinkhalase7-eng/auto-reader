from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Conversation, Message, User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.phone_call_repository import PhoneCallRepository
from app.repositories.reminder_repository import ReminderRepository
from app.schemas.pavi import ScheduleItem, UpcomingScheduleOut
from app.services.reminder_service import ReminderService
from app.services.appointment_service import AppointmentService
from app.utils.datetime import format_local, from_utc, now_utc
from app.utils.pavi_name import canonicalize_pavi_spelling


class ConversationService:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self.repo = ConversationRepository(db)

    async def list(self) -> list[Conversation]:
        return await self.repo.list_for_user(self.user.id)

    async def get(self, conversation_id: str) -> Conversation | None:
        return await self.repo.get(conversation_id, self.user.id)

    async def ensure(self, conversation_id: str | None, first_message: str) -> Conversation:
        if conversation_id:
            existing = await self.get(conversation_id)
            if existing:
                return existing
        title = canonicalize_pavi_spelling(first_message.strip().split("\n")[0][:80]) or "New conversation"
        row = Conversation(user_id=self.user.id, title=title)
        await self.repo.add_conversation(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def add_message(self, conversation: Conversation, role: str, content: str, message_type: str = "text") -> Message:
        msg = Message(conversation_id=conversation.id, role=role, content=content, message_type=message_type)
        await self.repo.add_message(msg)
        conversation.title = conversation.title or content[:80]
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def history(self, conversation_id: str, limit: int | None = None) -> list[tuple[str, str]]:
        settings = get_settings()
        rows = await self.repo.messages(conversation_id, limit=limit or settings.pavi_context_messages)
        out: list[tuple[str, str]] = []
        for row in rows:
            text = row.content if len(row.content) <= 500 else row.content[:497] + "..."
            out.append((row.role, text))
        return out

    async def detail_messages(self, conversation_id: str) -> list[Message]:
        return await self.repo.messages(conversation_id, limit=200)


async def upcoming_schedule(db: AsyncSession, user: User) -> UpcomingScheduleOut:
    settings = get_settings()
    from app.services.preference_service import PreferenceService

    pref = await PreferenceService(db, user).get()
    tz = pref.timezone
    reminders = await ReminderService(db, user).list(upcoming_only=True)
    appointments = await AppointmentService(db, user).list(upcoming_only=True)
    items: list[ScheduleItem] = []
    for r in reminders:
        items.append(
            ScheduleItem(
                id=r.id,
                kind="reminder",
                title=r.title,
                when_utc=r.reminder_time_utc,
                when_label=format_local(r.reminder_time_utc, r.timezone, with_date=False),
                timezone=r.timezone,
                phone_call_enabled=r.phone_call_enabled,
                status=r.status,
            )
        )
    for a in appointments:
        items.append(
            ScheduleItem(
                id=a.id,
                kind="appointment",
                title=a.title,
                when_utc=a.appointment_time_utc,
                when_label=format_local(a.appointment_time_utc, a.timezone, with_date=False),
                timezone=a.timezone,
                phone_call_enabled=a.phone_call_enabled,
                status=a.status,
                location=a.location,
            )
        )
    items.sort(key=lambda i: i.when_utc)
    now_local = from_utc(now_utc(), tz)
    today, tomorrow, later = [], [], []
    for item in items:
        local = from_utc(item.when_utc, tz)
        delta = (local.date() - now_local.date()).days
        if delta <= 0:
            today.append(item)
        elif delta == 1:
            tomorrow.append(item)
        else:
            later.append(item)
    return UpcomingScheduleOut(timezone=tz, items=items, today=today, tomorrow=tomorrow, later=later)


async def pavi_stats(db: AsyncSession, user: User) -> dict:
    rem = await ReminderRepository(db).counts(user.id)
    calls = await PhoneCallRepository(db).counts(user.id)
    return {**rem, **calls}
