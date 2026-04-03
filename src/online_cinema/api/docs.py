import secrets

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from online_cinema.core.config import get_settings

docs_security = HTTPBasic()


def _authorize_docs(credentials: HTTPBasicCredentials = Depends(docs_security)) -> None:
    settings = get_settings()
    is_valid = secrets.compare_digest(
        credentials.username, settings.docs_username
    ) and secrets.compare_digest(credentials.password, settings.docs_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid documentation credentials.",
            headers={"WWW-Authenticate": "Basic"},
        )


def register_docs(app: FastAPI) -> None:
    @app.get(
        "/openapi.json",
        include_in_schema=False,
        dependencies=[Depends(_authorize_docs)],
    )
    async def openapi_json() -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.get("/docs", include_in_schema=False, dependencies=[Depends(_authorize_docs)])
    async def swagger_ui() -> Response:
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - Swagger UI",
        )

    @app.get("/redoc", include_in_schema=False, dependencies=[Depends(_authorize_docs)])
    async def redoc_ui() -> Response:
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - ReDoc",
        )
