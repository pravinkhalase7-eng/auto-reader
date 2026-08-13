from __future__ import annotations

import logging

from app.core.sync_database import SyncSessionLocal
from app.repositories.reminder_repository import SyncReminderRepository
from app.utils.datetime import now_utc
from app.workers.celery_app import celery_app
from app.workers.reminder_tasks import process_reminder

logger = logging.getLogger("app.pavi.beat")


@celery_app.task(name="app.workers.beat_tasks.scan_due_reminders")
def scan_due_reminders() -> int:
    session = SyncSessionLocal()
    try:
        claimed = SyncReminderRepository(session).claim_due(now_utc())
        for reminder in claimed:
            logger.info("[REMINDER] id=%s status=processing queued", reminder.id)
            process_reminder.delay(reminder.id)
        return len(claimed)
    finally:
        session.close()


def scan_due_reminders_inline() -> int:
    """Process due reminders in-process so local API can place calls without Celery."""
    from app.workers.reminder_tasks import process_reminder_now

    session = SyncSessionLocal()
    try:
        claimed = SyncReminderRepository(session).claim_due(now_utc())
        for reminder in claimed:
            logger.info("[REMINDER] id=%s status=processing inline", reminder.id)
            process_reminder_now(reminder.id)
        return len(claimed)
    finally:
        session.close()
