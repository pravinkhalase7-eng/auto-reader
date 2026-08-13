from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.reminder import ReminderCreate, ReminderOut, ReminderUpdate
from app.services.reminder_service import ReminderService, to_out

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.post("", response_model=ReminderOut)
async def create_reminder(
    body: ReminderCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idempotency_key and not body.idempotency_key:
        body.idempotency_key = idempotency_key
    row = await ReminderService(db, user).create(body)
    return to_out(row)


@router.get("", response_model=list[ReminderOut])
async def list_reminders(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await ReminderService(db, user).list()
    return [to_out(r) for r in rows]


@router.get("/upcoming", response_model=list[ReminderOut])
async def upcoming_reminders(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await ReminderService(db, user).list(upcoming_only=True)
    return [to_out(r) for r in rows]


@router.get("/{reminder_id}", response_model=ReminderOut)
async def get_reminder(reminder_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await ReminderService(db, user).get(reminder_id)
    return to_out(row)


@router.patch("/{reminder_id}", response_model=ReminderOut)
async def update_reminder(
    reminder_id: str,
    body: ReminderUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await ReminderService(db, user).update(reminder_id, body)
    return to_out(row)


@router.delete("/{reminder_id}", response_model=ReminderOut)
async def cancel_reminder(reminder_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await ReminderService(db, user).cancel(reminder_id)
    return to_out(row)
