"""Test fixtures.

By default, tests run against PostgreSQL via `TEST_DATABASE_URL` (or local PostgreSQL on port 5433).
If no PostgreSQL server is available, it gracefully falls back to SQLite in-memory for unit tests,
while clearly logging the mode.
"""
import os

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import Settings
from app.database.connection import DatabaseManager
from app.database.indexes import ensure_indexes
from app.database.tables import metadata
from app.main import create_app
from app.services.department_routing_service import DepartmentRoutingService
from tests.helpers import World

TEST_SECRET = "test-secret-key-that-is-long-enough-1234567890"
DEFAULT_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres@127.0.0.1:5433/postgres",
)


def make_settings(**overrides) -> Settings:
    base = dict(
        database_url=overrides.get("database_url", DEFAULT_TEST_DB_URL),
        database_name="nivara_test",
        jwt_secret=TEST_SECRET,
        environment="test",
        bcrypt_rounds=4,
        rate_limit_enabled=False,
        background_jobs_enabled=False,
        app_timezone="UTC",
        cors_origins=["http://localhost:5173"],
        log_level="WARNING",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest_asyncio.fixture
async def db(settings):
    manager = DatabaseManager(settings)
    database = await manager.connect()

    async with database.engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        if "postgresql" in settings.database_url:
            table_names = ", ".join(f'"{t.name}"' for t in metadata.sorted_tables)
            await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE;"))
        else:
            for t in reversed(metadata.sorted_tables):
                await conn.execute(t.delete())

    yield database

    # Clean up all tables after each test
    async with database.engine.begin() as conn:
        if "postgresql" in settings.database_url:
            table_names = ", ".join(f'"{t.name}"' for t in metadata.sorted_tables)
            await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE;"))
        else:
            for t in reversed(metadata.sorted_tables):
                await conn.execute(t.delete())

    await manager.close()


@pytest_asyncio.fixture
async def app(settings, db):
    application = create_app(settings, db=db)
    await ensure_indexes(db)
    await DepartmentRoutingService(db).ensure_default_rules()
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def world(client, db, settings) -> World:
    w = World(client, db, settings)
    await w.build()
    return w
