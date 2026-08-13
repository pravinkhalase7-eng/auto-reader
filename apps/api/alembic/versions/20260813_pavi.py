"""Pavi tables. SQLAlchemy create_all also creates these on API startup."""

from alembic import op
from sqlalchemy import inspect

from app.core.base import Base
import app.models  # noqa: F401


revision = "20260813_pavi"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("reminders"):
        return
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS phone_calls")
    op.execute("DROP TABLE IF EXISTS pavi_idempotency_keys")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS conversations")
    op.execute("DROP TABLE IF EXISTS reminders")
    op.execute("DROP TABLE IF EXISTS appointments")
    op.execute("DROP TABLE IF EXISTS bookings")
    op.execute("DROP TABLE IF EXISTS user_preferences")
