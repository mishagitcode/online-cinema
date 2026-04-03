from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from online_cinema.api.docs import register_docs
from online_cinema.api.router import api_router
from online_cinema.core.config import get_settings
from online_cinema.db.init_db import init_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_database()
    yield


def create_application() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Online Cinema API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    register_docs(app)
    return app


app = create_application()
