from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "docvault",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,
    task_time_limit=900,
    task_default_retry_delay=60,
    task_max_retries=3,
    task_routes={
        "app.tasks.pdf_processing.*": {"queue": "pdf_processing"},
    },
    beat_schedule={
        "tag-evolution-daily": {
            "task": "app.tasks.tag_evolution.run_tag_evolution",
            "schedule": crontab(hour=3, minute=0),  # Every day at 3:00 AM
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])

# Ensure tasks are registered when this module is imported by the worker
import app.tasks.pdf_processing  # noqa: F401, E402
import app.tasks.tag_evolution  # noqa: F401, E402
