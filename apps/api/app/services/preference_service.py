from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import User, UserPreference
from app.repositories.conversation_repository import PreferenceRepository
from app.schemas.pavi import PreferenceIn, PreferenceOut
from app.utils.phone import mask_phone, validate_phone


def preference_to_out(pref: UserPreference) -> PreferenceOut:
    return PreferenceOut(
        phone_number=pref.phone_number,
        phone_number_masked=mask_phone(pref.phone_number),
        phone_call_enabled=pref.phone_call_enabled,
        preferred_language=pref.preferred_language,
        timezone=pref.timezone,
    )


class PreferenceService:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self.repo = PreferenceRepository(db)
        self.settings = get_settings()

    async def get(self) -> UserPreference:
        return await self.repo.get_or_create(
            self.user.id,
            timezone=self.settings.default_timezone,
            language=self.user.ui_language or "en",
        )

    async def update(self, body: PreferenceIn) -> UserPreference:
        pref = await self.get()
        if body.phone_number is not None:
            if body.phone_number.strip():
                try:
                    pref.phone_number = validate_phone(body.phone_number)
                except ValueError as exc:
                    raise AppError(str(exc), code="INVALID_PHONE") from exc
            else:
                pref.phone_number = None
        if body.phone_call_enabled is not None:
            pref.phone_call_enabled = body.phone_call_enabled
        if body.preferred_language:
            pref.preferred_language = body.preferred_language
        if body.timezone:
            from app.utils.datetime import get_zone

            try:
                get_zone(body.timezone)
            except Exception as exc:  # noqa: BLE001
                raise AppError("That timezone isn't valid. Try Asia/Kolkata.") from exc
            pref.timezone = body.timezone
        await self.db.commit()
        await self.db.refresh(pref)
        return pref
