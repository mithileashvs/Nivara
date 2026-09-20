import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import Settings

logger = logging.getLogger("smartcare.db")

# Alias so services do not depend on a concrete driver class (tests use an in-memory one).
Database = AsyncIOMotorDatabase


class MongoManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.client: AsyncIOMotorClient | None = None
        self.db: Any = None

    async def connect(self) -> Any:
        self.client = AsyncIOMotorClient(
            self._settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
            uuidRepresentation="standard",
        )
        self.db = self.client[self._settings.database_name]
        await self.client.admin.command("ping")  # fail fast if MongoDB is unreachable
        logger.info("Connected to MongoDB database '%s'", self._settings.database_name)
        return self.db

    async def close(self) -> None:
        if self.client is not None:
            self.client.close()
            logger.info("MongoDB connection closed")
