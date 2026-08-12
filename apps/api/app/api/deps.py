from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.logging import user_id_ctx
from app.core.security import safe_decode_token
from app.models import User


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError()
    token = authorization.split(" ", 1)[1]
    payload = safe_decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError()
    user = await db.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.profile))
    )
    if not user or not user.is_active:
        raise UnauthorizedError()
    user_id_ctx.set(user.id)
    return user
