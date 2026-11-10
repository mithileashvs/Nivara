"""Phase 1 Database Migration Script for Nivara.

Applies schema updates to Supabase PostgreSQL:
1. Allows RESCHEDULE_REQUESTED status on appointments
2. Extends appointment_history with structured scheduling metadata
3. Creates rescheduling_requests table with indexes and constraints
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
logger = logging.getLogger("nivara.migration_phase1")


async def run_migration() -> None:
    settings = get_settings()
    manager = DatabaseManager(settings)
    logger.info("Connecting to database: %s", settings.database_name)
    try:
        db = await manager.connect()
        sql_file = Path(__file__).resolve().parent / "migration_phase1.sql"
        if not sql_file.exists():
            raise FileNotFoundError(f"Migration script not found: {sql_file}")

        migration_sql = sql_file.read_text(encoding="utf-8")

        async with db.engine.begin() as conn:
            dialect = db.engine.dialect.name
            if dialect == "postgresql":
                logger.info("Executing Phase 1 migration SQL from %s...", sql_file.name)
                raw_conn = await conn.get_raw_connection()
                await raw_conn.driver_connection.execute(migration_sql)
            else:
                logger.info("Non-PostgreSQL dialect (%s): running metadata.create_all...", dialect)
                from app.database.tables import metadata
                await conn.run_sync(metadata.create_all)
        logger.info("Phase 1 migration completed successfully!")
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
