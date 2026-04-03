from celery import Celery  # type: ignore[import-untyped]

from online_cinema.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "online_cinema",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.beat_schedule = {}
