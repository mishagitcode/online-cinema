import pytest


@pytest.mark.asyncio
async def test_health_check(client) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
