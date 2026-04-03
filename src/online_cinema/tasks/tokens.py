import asyncio

from online_cinema.core.celery_app import celery_app
from online_cinema.db.session import SessionLocal
from online_cinema.services.auth import cleanup_expired_tokens


@celery_app.task(name="cleanup_expired_tokens")
def cleanup_expired_tokens_task() -> int:
    async def _run() -> int:
        async with SessionLocal() as session:
            return await cleanup_expired_tokens(session)

    return asyncio.run(_run())
