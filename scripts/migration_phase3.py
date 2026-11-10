"""Nivara Phase 3 Migration Runner

Applies database updates for Phase 3 from `scripts/migration_phase3.sql`:
- Creates waitlist_offers table with foreign keys, constraints, and indexes.
- Reconciles schema for prior Phase 3 iterations (slot_id nullable with SET NULL, reason, canonical created_at).
- Safely migrates legacy offered_at to created_at.
- Reconciles status CHECK constraint on waitlist_offers without error suppression.
- Reconciles and verifies foreign key from appointment_slots.waitlist_offer_id to waitlist_offers(id) with ON DELETE SET NULL.
- Idempotently updates appointment_slots with held_until and waitlist_offer_id.
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
logger = logging.getLogger("nivara.migration_phase3")


async def run_migration() -> None:
    settings = get_settings()
    manager = DatabaseManager(settings)
    logger.info("Connecting to database: %s", settings.database_name)
    try:
        db = await manager.connect()
        sql_file = Path(__file__).resolve().parent / "migration_phase3.sql"
        if not sql_file.exists():
            raise FileNotFoundError(f"Migration script not found: {sql_file}")

        migration_sql = sql_file.read_text(encoding="utf-8")

        async with db.engine.begin() as conn:
            dialect = db.engine.dialect.name
            if dialect == "postgresql":
                logger.info("Executing Phase 3 migration SQL from %s...", sql_file.name)
                raw_conn = await conn.get_raw_connection()
                await raw_conn.driver_connection.execute(migration_sql)
            else:
                from app.database.tables import metadata
                await conn.run_sync(metadata.create_all)
        logger.info("Phase 3 migration applied successfully!")
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
