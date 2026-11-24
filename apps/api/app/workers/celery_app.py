from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "flatmate_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Reliability: ack after the task finishes so a crashed worker's task is redelivered,
    # and prefetch one at a time so long tasks don't starve others.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=300,
    task_soft_time_limit=240,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    beat_schedule={
        # Sweeps the outbox. Requests also kick a dispatch right after responding, so this
        # mostly catches retries and anything left behind by a crash.
        "outbox-dispatch": {"task": "outbox.dispatch", "schedule": 15.0},
        "maintenance-hourly": {"task": "maintenance.run", "schedule": crontab(minute=7)},
        # Mondays 03:30 UTC: retrain the recommendation ranker from the past week's likes/passes.
        "ml-train-ranker-weekly": {"task": "ml.train_ranker", "schedule": crontab(minute=30, hour=3, day_of_week=1)},
    },
)
