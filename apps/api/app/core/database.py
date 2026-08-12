from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_TTS_WORD_FK_PATCH = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tts_word_timings_word_id_fkey') THEN
    ALTER TABLE tts_word_timings DROP CONSTRAINT tts_word_timings_word_id_fkey;
  END IF;
  ALTER TABLE tts_word_timings
    ADD CONSTRAINT tts_word_timings_word_id_fkey
    FOREIGN KEY (word_id) REFERENCES lesson_words(id) ON DELETE CASCADE;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tts_word_timings_audio_asset_id_fkey') THEN
    ALTER TABLE tts_word_timings DROP CONSTRAINT tts_word_timings_audio_asset_id_fkey;
  END IF;
  ALTER TABLE tts_word_timings
    ADD CONSTRAINT tts_word_timings_audio_asset_id_fkey
    FOREIGN KEY (audio_asset_id) REFERENCES audio_assets(id) ON DELETE CASCADE;
END $$;
"""


async def apply_schema_patches(bind) -> None:
    """Existing Postgres DBs were created without ON DELETE CASCADE on timings."""
    dialect = getattr(getattr(bind, "dialect", None), "name", "") or ""
    url = str(settings.database_url)
    if dialect != "postgresql" and not url.startswith("postgresql"):
        return
    await bind.execute(text(_TTS_WORD_FK_PATCH))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
