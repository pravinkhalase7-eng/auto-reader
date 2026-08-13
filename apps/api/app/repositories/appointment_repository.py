from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appointment, Booking
from app.utils.datetime import now_utc


class AppointmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, appointment_id: str, user_id: str) -> Appointment | None:
        return await self.db.scalar(
            select(Appointment).where(Appointment.id == appointment_id, Appointment.user_id == user_id)
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
    ) -> list[Appointment]:
        stmt = select(Appointment).where(Appointment.user_id == user_id)
        if not include_cancelled:
            stmt = stmt.where(Appointment.status != "cancelled")
        if upcoming_only:
            stmt = stmt.where(Appointment.appointment_time_utc >= now_utc(), Appointment.status == "scheduled")
        if start:
            stmt = stmt.where(Appointment.appointment_time_utc >= start)
        if end:
            stmt = stmt.where(Appointment.appointment_time_utc < end)
        stmt = stmt.order_by(Appointment.appointment_time_utc.asc()).limit(limit)
        return list((await self.db.scalars(stmt)).all())

    async def add(self, appointment: Appointment) -> Appointment:
        self.db.add(appointment)
        await self.db.flush()
        return appointment


class BookingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, booking_id: str, user_id: str) -> Booking | None:
        return await self.db.scalar(select(Booking).where(Booking.id == booking_id, Booking.user_id == user_id))

    async def list_for_user(self, user_id: str, *, upcoming_only: bool = False, limit: int = 50) -> list[Booking]:
        stmt = select(Booking).where(Booking.user_id == user_id, Booking.status != "cancelled")
        if upcoming_only:
            stmt = stmt.where(Booking.booking_time_utc >= now_utc())
        stmt = stmt.order_by(Booking.booking_time_utc.asc()).limit(limit)
        return list((await self.db.scalars(stmt)).all())

    async def add(self, booking: Booking) -> Booking:
        self.db.add(booking)
        await self.db.flush()
        return booking
