from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("pavi")
celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    beat_schedule={
        "scan-due-reminders": {
            "task": "app.workers.beat_tasks.scan_due_reminders",
            "schedule": float(settings.reminder_scan_interval_seconds),
        }
    },
    imports=("app.workers.reminder_tasks", "app.workers.beat_tasks"),
)
