from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import AppError, to_http_exception
from app.core.security import create_access_token, hash_password, verify_password
from app.models import StudentProfile, User
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email.lower()))
    if existing:
        raise to_http_exception(AppError("An account with this email already exists.", code="EMAIL_EXISTS"))
    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role="STUDENT",
    )
    db.add(user)
    await db.flush()
    db.add(StudentProfile(user_id=user.id, class_level=body.class_level))
    await db.commit()
    user = await db.scalar(select(User).where(User.id == user.id).options(selectinload(User.profile)))
    assert user
    token = create_access_token(user.id, extra={"role": user.role})
    return AuthResponse(user=UserOut.model_validate(user), access_token=token)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(
        select(User).where(User.email == body.email.lower()).options(selectinload(User.profile))
    )
    if not user or not verify_password(body.password, user.hashed_password):
        raise to_http_exception(AppError("Email or password looks incorrect.", code="INVALID_CREDENTIALS", status_code=401))
    token = create_access_token(user.id, extra={"role": user.role})
    return AuthResponse(user=UserOut.model_validate(user), access_token=token)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)
