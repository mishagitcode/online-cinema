from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]

from online_cinema.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "online_cinema",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.beat_schedule = {
    "cleanup-expired-tokens-hourly": {
        "task": "cleanup_expired_tokens",
        "schedule": crontab(minute=0),
    }
}
celery_app.autodiscover_tasks(["online_cinema.tasks"])
