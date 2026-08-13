from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()


def _engine_kwargs() -> dict:
    kwargs: dict = {"echo": False, "future": True}
    if "sqlite" in settings.database_url:
        kwargs["connect_args"] = {"timeout": 30, "check_same_thread": False}
        kwargs["poolclass"] = NullPool
    return kwargs


engine = create_async_engine(settings.database_url, **_engine_kwargs())


@event.listens_for(engine.sync_engine, "connect")
def _sqlite_on_connect(dbapi_connection, _connection_record) -> None:
    if "sqlite" not in settings.database_url:
        return
    raw = dbapi_connection
    for attr in ("_connection", "driver_connection", "_conn"):
        inner = getattr(raw, attr, None)
        if inner is not None:
            raw = inner
    sqlite_conn = getattr(raw, "_conn", raw)
    try:
        sqlite_conn.execute("PRAGMA journal_mode=WAL")
        sqlite_conn.execute("PRAGMA busy_timeout=30000")
        sqlite_conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


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
    """Keep older databases in sync without a full migration tool."""
    dialect = getattr(getattr(bind, "dialect", None), "name", "") or ""
    url = str(settings.database_url)
    is_postgres = dialect == "postgresql" or url.startswith("postgresql")
    is_sqlite = dialect == "sqlite" or "sqlite" in url
    if is_postgres:
        await bind.execute(text(_TTS_WORD_FK_PATCH))
        await bind.execute(
            text(
                "ALTER TABLE lesson_illustrations "
                "ADD COLUMN IF NOT EXISTS portrait_storage_key VARCHAR(512) DEFAULT ''"
            )
        )
        return
    if is_sqlite:
        rows = await bind.execute(text("PRAGMA table_info(lesson_illustrations)"))
        cols = {row[1] for row in rows}
        if cols and "portrait_storage_key" not in cols:
            await bind.execute(
                text(
                    "ALTER TABLE lesson_illustrations "
                    "ADD COLUMN portrait_storage_key VARCHAR(512) DEFAULT ''"
                )
            )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
