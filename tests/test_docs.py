import base64

import pytest


def basic_auth_header(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.mark.asyncio
async def test_docs_require_basic_auth(client) -> None:
    unauthorized_response = await client.get("/docs")
    authorized_response = await client.get(
        "/docs",
        headers=basic_auth_header("docs-user", "docs-pass"),
    )
    openapi_response = await client.get(
        "/openapi.json",
        headers=basic_auth_header("docs-user", "docs-pass"),
    )

    assert unauthorized_response.status_code == 401
    assert authorized_response.status_code == 200
    assert openapi_response.status_code == 200
