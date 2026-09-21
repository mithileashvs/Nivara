"""PostgreSQL / Supabase async database connection manager for Nivara."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings
from app.database.session import Database

logger = logging.getLogger("nivara.db")


def normalize_database_url(url: str) -> str:
    """Normalize Supabase / PostgreSQL database URLs for asyncpg driver."""
    url = url.strip()
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


class DatabaseManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.engine: AsyncEngine | None = None
        self.db: Database | None = None

    async def connect(self) -> Database:
        url = normalize_database_url(self._settings.database_url)
        # Configure engine options based on driver
        connect_args: dict[str, Any] = {}
        if url.startswith("postgresql+asyncpg://"):
            # asyncpg connection settings
            connect_args = {"server_settings": {"timezone": "UTC"}}

        self.engine = create_async_engine(
            url,
            connect_args=connect_args,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
        )
        self.db = Database(self.engine)
        if "postgresql" in url:
            from sqlalchemy import text
            async with self.engine.connect() as c1:
                await c1.execute(text("SELECT 1;"))
            async with self.engine.connect() as c1, self.engine.connect() as c2, self.engine.connect() as c3:
                await c1.execute(text("SELECT 1;"))
                await c2.execute(text("SELECT 1;"))
                await c3.execute(text("SELECT 1;"))
        logger.info("Connected to database (%s)", url.split("@")[-1] if "@" in url else url)
        return self.db

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
            logger.info("Database connection closed")
