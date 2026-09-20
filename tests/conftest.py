"""Test fixtures.

By default tests run against an in-memory MongoDB-compatible driver (mongomock-motor), so no server is
needed. To run the SAME suite against a real MongoDB, set ``TEST_MONGODB_URI`` (a throwaway database
is created and dropped per test):

    TEST_MONGODB_URI=mongodb://localhost:27017 pytest
"""
import os
import uuid

import httpx
import pytest
import pytest_asyncio

from app.core.config import Settings
from app.database.indexes import ensure_indexes
from app.main import create_app
from app.services.department_routing_service import DepartmentRoutingService
from tests.helpers import World

TEST_SECRET = "test-secret-key-that-is-long-enough-1234567890"


def make_settings(**overrides) -> Settings:
    base = dict(
        mongodb_uri="mongodb://unused", database_name="smartcare_test", jwt_secret=TEST_SECRET, environment="test",
        bcrypt_rounds=4, rate_limit_enabled=False, background_jobs_enabled=False, app_timezone="UTC",
        cors_origins=["http://localhost:5173"], log_level="WARNING",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest_asyncio.fixture
async def db():
    uri = os.environ.get("TEST_MONGODB_URI")
    if uri:
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(uri, tz_aware=False)
        name = f"smartcare_test_{uuid.uuid4().hex[:8]}"
        database = client[name]
        yield database
        await client.drop_database(name)
        client.close()
    else:
        from mongomock_motor import AsyncMongoMockClient

        yield AsyncMongoMockClient()["smartcare_test"]


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
