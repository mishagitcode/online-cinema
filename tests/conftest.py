import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["TEST_DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-with-safe-length-1234567890"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"

from online_cinema.db.base import Base
from online_cinema.db.init_db import seed_database
from online_cinema.db.session import SessionLocal, engine
from online_cinema.main import app
from online_cinema.services.email import email_service


@pytest.fixture(autouse=True)
async def prepare_database() -> AsyncIterator[None]:
    email_service.sent_messages.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        await seed_database(session)

    yield

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest.fixture
async def db_session() -> AsyncIterator[SessionLocal]:
    async with SessionLocal() as session:
        yield session
