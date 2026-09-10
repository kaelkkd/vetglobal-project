import asyncio
import os
import sys
from collections.abc import AsyncIterator, Iterator
from contextlib import AsyncExitStack

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://vetglobal:vetglobal@localhost:5433/vetglobal_test",
)
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-internal-token-value")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from vetglobal.config import Settings  # noqa: E402
from vetglobal.main import create_app  # noqa: E402


def _test_database_url() -> str:
    url = os.environ["TEST_DATABASE_URL"]
    database = make_url(url).database or ""
    if "test" not in database.lower():
        raise RuntimeError("Refusing to run tests against a database not named as a test database")
    return url


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[str]:
    url = _test_database_url()
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield url
    command.downgrade(config, "base")
    if previous_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_url


@pytest.fixture(autouse=True)
def clean_database(migrated_database: str) -> Iterator[None]:
    engine = create_engine(migrated_database)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE jobs, documents, pets RESTART IDENTITY CASCADE"))
    yield
    engine.dispose()


@pytest.fixture
def test_settings(migrated_database: str) -> Settings:
    return Settings(
        database_url=migrated_database,
        internal_service_token="test-internal-token-value",
        allowed_frontend_origins=["http://localhost:5173"],
        max_file_size_bytes=256,
        max_request_body_bytes=1024,
        polling_timeout_seconds=0.25,
        polling_interval_seconds=0.01,
    )


@pytest.fixture
async def app_client(test_settings: Settings) -> AsyncIterator[tuple[FastAPI, AsyncClient]]:
    app = create_app(test_settings)
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
            yield app, test_client


@pytest.fixture
async def client(app_client: tuple[FastAPI, AsyncClient]) -> AsyncClient:
    return app_client[1]


@pytest.fixture
async def client_pair(test_settings: Settings) -> AsyncIterator[tuple[AsyncClient, AsyncClient]]:
    apps = (create_app(test_settings), create_app(test_settings))
    async with AsyncExitStack() as stack:
        clients: list[AsyncClient] = []
        for app in apps:
            await stack.enter_async_context(app.router.lifespan_context(app))
            clients.append(
                await stack.enter_async_context(
                    AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
                )
            )
        yield clients[0], clients[1]
