from datetime import datetime
from hashlib import sha256

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models import Appointment, Booking, PaviIdempotencyKey, Reminder
from app.utils.datetime import now_utc


class ReminderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, reminder_id: str, user_id: str) -> Reminder | None:
        return await self.db.scalar(
            select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
        )

    async def get_by_idempotency(self, user_id: str, key: str) -> Reminder | None:
        return await self.db.scalar(
            select(Reminder).where(Reminder.user_id == user_id, Reminder.idempotency_key == key)
        )

    async def list_for_user(
        self,
        user_id: str,
        *,
        upcoming_only: bool = False,
        include_cancelled: bool = False,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
    ) -> list[Reminder]:
        stmt: Select = select(Reminder).where(Reminder.user_id == user_id)
        if not include_cancelled:
            stmt = stmt.where(Reminder.status.notin_(["cancelled"]))
        stmt = (
            stmt.outerjoin(Appointment, Reminder.appointment_id == Appointment.id)
            .outerjoin(Booking, Reminder.booking_id == Booking.id)
            .where(
                or_(Reminder.appointment_id.is_(None), Appointment.status != "cancelled"),
                or_(Reminder.booking_id.is_(None), Booking.status != "cancelled"),
            )
        )
        if upcoming_only:
            stmt = stmt.where(
                Reminder.status.in_(["pending", "scheduled"]),
                Reminder.reminder_time_utc >= now_utc(),
            )
        if start:
            stmt = stmt.where(Reminder.reminder_time_utc >= start)
        if end:
            stmt = stmt.where(Reminder.reminder_time_utc < end)
        stmt = stmt.order_by(Reminder.reminder_time_utc.asc()).limit(limit)
        return list((await self.db.scalars(stmt)).unique().all())

    async def cancel_active_linked(
        self,
        user_id: str,
        *,
        appointment_id: str | None = None,
        booking_id: str | None = None,
    ) -> int:
        if not appointment_id and not booking_id:
            return 0
        conditions = [
            Reminder.user_id == user_id,
            Reminder.status.in_(["pending", "scheduled", "processing", "calling"]),
        ]
        if appointment_id:
            conditions.append(Reminder.appointment_id == appointment_id)
        else:
            conditions.append(Reminder.booking_id == booking_id)
        result = await self.db.execute(
            update(Reminder).where(and_(*conditions)).values(status="cancelled", cancelled_at=now_utc())
        )
        return int(result.rowcount or 0)

    async def add(self, reminder: Reminder) -> Reminder:
        self.db.add(reminder)
        await self.db.flush()
        return reminder

    async def counts(self, user_id: str) -> dict[str, int]:
        total = await self.db.scalar(select(func.count()).select_from(Reminder).where(Reminder.user_id == user_id))
        pending = await self.db.scalar(
            select(func.count())
            .select_from(Reminder)
            .where(Reminder.user_id == user_id, Reminder.status.in_(["pending", "scheduled", "processing"]))
        )
        completed = await self.db.scalar(
            select(func.count()).select_from(Reminder).where(Reminder.user_id == user_id, Reminder.status == "completed")
        )
        failed = await self.db.scalar(
            select(func.count()).select_from(Reminder).where(Reminder.user_id == user_id, Reminder.status == "failed")
        )
        return {
            "total_reminders": int(total or 0),
            "pending_reminders": int(pending or 0),
            "completed_reminders": int(completed or 0),
            "failed_reminders": int(failed or 0),
        }


class SyncReminderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, reminder_id: str) -> Reminder | None:
        return self.db.get(Reminder, reminder_id)

    def claim_due(self, now: datetime, limit: int = 25) -> list[Reminder]:
        stmt = (
            select(Reminder)
            .where(
                Reminder.status == "scheduled",
                Reminder.reminder_time_utc <= now,
            )
            .order_by(Reminder.reminder_time_utc.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        try:
            rows = list(self.db.scalars(stmt).all())
        except Exception:
            rows = list(
                self.db.scalars(
                    select(Reminder)
                    .where(Reminder.status == "scheduled", Reminder.reminder_time_utc <= now)
                    .order_by(Reminder.reminder_time_utc.asc())
                    .limit(limit)
                ).all()
            )
        claimed: list[Reminder] = []
        for row in rows:
            result = self.db.execute(
                update(Reminder)
                .where(Reminder.id == row.id, Reminder.status == "scheduled")
                .values(status="processing")
            )
            if result.rowcount:
                row.status = "processing"
                claimed.append(row)
        self.db.commit()
        for row in claimed:
            self.db.refresh(row)
        return claimed


async def remember_idempotency(db: AsyncSession, user_id: str, key: str, resource_type: str, resource_id: str) -> None:
    db.add(
        PaviIdempotencyKey(user_id=user_id, key=key, resource_type=resource_type, resource_id=resource_id)
    )
    await db.flush()


def operation_key(user_id: str, title: str, when_iso: str) -> str:
    raw = f"{user_id}|{title.strip().lower()}|{when_iso}"
    return sha256(raw.encode()).hexdigest()[:40]
