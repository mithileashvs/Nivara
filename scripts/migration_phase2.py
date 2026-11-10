"""Nivara Phase 2 Migration Runner

Applies database updates for Phase 2:
- Adds category, action_url, read_at columns to notifications table.
- Creates notification_preferences table with unique constraint and indexes.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.database.connection import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nivara.migration_phase2")


async def run_migration() -> None:
    settings = get_settings()
    manager = DatabaseManager(settings)
    logger.info("Connecting to database: %s", settings.database_name)
    try:
        db = await manager.connect()
        sql_file = Path(__file__).resolve().parent / "migration_phase2.sql"
        if not sql_file.exists():
            raise FileNotFoundError(f"Migration script not found: {sql_file}")

        migration_sql = sql_file.read_text(encoding="utf-8")

        async with db.engine.begin() as conn:
            dialect = db.engine.dialect.name
            if dialect == "postgresql":
                logger.info("Executing Phase 2 migration SQL from %s...", sql_file.name)
                raw_conn = await conn.get_raw_connection()
                await raw_conn.driver_connection.execute(migration_sql)
            else:
                from app.database.tables import metadata
                await conn.run_sync(metadata.create_all)
        logger.info("Phase 2 migration applied successfully!")
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
