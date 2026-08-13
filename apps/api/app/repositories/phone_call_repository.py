from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models import PhoneCall


class PhoneCallRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_user(self, user_id: str, limit: int = 30) -> list[PhoneCall]:
        stmt = (
            select(PhoneCall)
            .where(PhoneCall.user_id == user_id)
            .order_by(PhoneCall.created_at.desc())
            .limit(limit)
        )
        return list((await self.db.scalars(stmt)).all())

    async def get_by_sid(self, sid: str) -> PhoneCall | None:
        return await self.db.scalar(select(PhoneCall).where(PhoneCall.twilio_call_sid == sid))

    async def counts(self, user_id: str) -> dict[str, int]:
        made = await self.db.scalar(
            select(func.count()).select_from(PhoneCall).where(PhoneCall.user_id == user_id)
        )
        answered = await self.db.scalar(
            select(func.count())
            .select_from(PhoneCall)
            .where(PhoneCall.user_id == user_id, PhoneCall.status.in_(["in-progress", "completed"]))
        )
        failed = await self.db.scalar(
            select(func.count())
            .select_from(PhoneCall)
            .where(PhoneCall.user_id == user_id, PhoneCall.status.in_(["failed", "busy", "no-answer", "canceled"]))
        )
        return {
            "calls_made": int(made or 0),
            "calls_answered": int(answered or 0),
            "calls_failed": int(failed or 0),
        }

    async def add(self, call: PhoneCall) -> PhoneCall:
        self.db.add(call)
        await self.db.flush()
        return call


class SyncPhoneCallRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, call: PhoneCall) -> PhoneCall:
        self.db.add(call)
        self.db.flush()
        return call

    def get_by_sid(self, sid: str) -> PhoneCall | None:
        return self.db.scalar(select(PhoneCall).where(PhoneCall.twilio_call_sid == sid))

    def latest_for_reminder(self, reminder_id: str) -> PhoneCall | None:
        return self.db.scalar(
            select(PhoneCall)
            .where(PhoneCall.reminder_id == reminder_id)
            .order_by(PhoneCall.created_at.desc())
            .limit(1)
        )
