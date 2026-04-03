from fastapi import FastAPI

from online_cinema.api.router import api_router
from online_cinema.core.config import get_settings


def create_application() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Online Cinema API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_application()

