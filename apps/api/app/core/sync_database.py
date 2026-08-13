from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

sync_engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    future=True,
)
SyncSessionLocal = sessionmaker(bind=sync_engine, class_=Session, expire_on_commit=False)


def get_sync_session() -> Session:
    return SyncSessionLocal()
