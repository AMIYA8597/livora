import os
import ssl
from typing import Any, Dict, Optional

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_init, worker_ready, worker_shutdown

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry

configure_logging()
init_sentry("worker")  # Celery tasks are picked up by the SDK's Celery integration



def redis_tls_options(url: str) -> Optional[Dict[str, Any]]:
    """
    TLS settings for a rediss:// URL (managed Redis such as Memorystore with in-transit
    encryption, or Upstash). Celery refuses such a URL unless it says how to check the
    certificate, so verify it by default; a URL that sets ssl_cert_reqs itself is left alone.
    """
    if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
        return {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    return None


celery_app = Celery(
    "flatmate_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    # Keep our log handler (JSON in production) instead of Celery's own.
    worker_hijack_root_logger=False,
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
        # Mondays 04:00 UTC: retrain the listing ranker from what people were shown and opened.
        "ml-train-listing-ranker-weekly": {"task": "ml.train_listing_ranker", "schedule": crontab(minute=0, hour=4, day_of_week=1)},
    },
)

_broker_tls = redis_tls_options(settings.CELERY_BROKER_URL)
if _broker_tls:
    celery_app.conf.broker_use_ssl = _broker_tls
_backend_tls = redis_tls_options(settings.CELERY_RESULT_BACKEND)
if _backend_tls:
    celery_app.conf.redis_backend_use_ssl = _backend_tls


# app.workers.run serves the health check: it reports ready only once this file exists, i.e.
# the worker has reached the broker and is consuming.
@worker_init.connect
def _check_signing_key(**_: Any) -> None:
    # Tasks sign password-reset links and hash verification codes with SECRET_KEY.
    from app.core.security import require_signing_key
    require_signing_key()


@worker_ready.connect
def _mark_ready(**_: Any) -> None:
    path = os.environ.get("WORKER_READY_FILE")
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("ready")


@worker_shutdown.connect
def _clear_ready(**_: Any) -> None:
    path = os.environ.get("WORKER_READY_FILE")
    if path:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
