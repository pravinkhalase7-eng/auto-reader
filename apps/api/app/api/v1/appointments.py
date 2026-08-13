from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentOut,
    AppointmentUpdate,
    BookingCreate,
    BookingOut,
    BookingUpdate,
)
from app.services.appointment_service import (
    AppointmentService,
    BookingService,
    appointment_to_out,
    booking_to_out,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])
bookings_router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=AppointmentOut)
async def create_appointment(
    body: AppointmentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row, _reminder = await AppointmentService(db, user).create(body)
    return appointment_to_out(row)


@router.get("", response_model=list[AppointmentOut])
async def list_appointments(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await AppointmentService(db, user).list()
    return [appointment_to_out(r) for r in rows]


@router.patch("/{appointment_id}", response_model=AppointmentOut)
async def update_appointment(
    appointment_id: str,
    body: AppointmentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await AppointmentService(db, user).update(appointment_id, body)
    return appointment_to_out(row)


@router.delete("/{appointment_id}", response_model=AppointmentOut)
async def cancel_appointment(
    appointment_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await AppointmentService(db, user).cancel(appointment_id)
    return appointment_to_out(row)


@bookings_router.post("", response_model=BookingOut)
async def create_booking(body: BookingCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row, _ = await BookingService(db, user).create(body)
    return booking_to_out(row)


@bookings_router.get("", response_model=list[BookingOut])
async def list_bookings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await BookingService(db, user).list()
    return [booking_to_out(r) for r in rows]


@bookings_router.patch("/{booking_id}", response_model=BookingOut)
async def update_booking(
    booking_id: str,
    body: BookingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await BookingService(db, user).update(booking_id, body)
    return booking_to_out(row)


@bookings_router.delete("/{booking_id}", response_model=BookingOut)
async def cancel_booking(booking_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await BookingService(db, user).cancel(booking_id)
    return booking_to_out(row)
