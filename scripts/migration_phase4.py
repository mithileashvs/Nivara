"""Nivara Phase 4 Migration Runner

Applies database updates for Phase 4:
- Creates medical_documents table with foreign keys, constraints, and indexes.
- Creates document_shares table for patient-controlled doctor consent.
- Enforces partial unique index uq_document_shares_active on (document_id, doctor_id) WHERE consent_status = 'GRANTED'.
- Creates medical_record_audits table with ON DELETE SET NULL for permanent legal compliance audit trail.
- Reconciles existing Phase 4 tables idempotently.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.core.config import get_settings
from app.database.connection import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nivara.migration_phase4")


async def run_migration() -> None:
    settings = get_settings()
    manager = DatabaseManager(settings)
    logger.info("Connecting to database: %s", settings.database_name)
    try:
        db = await manager.connect()
    except Exception as exc:
        logger.error("Failed to connect to database: %s", exc)
        logger.info("You can run scripts/migration_phase4.sql directly in the Supabase SQL Editor.")
        return

    sql_file = Path(__file__).resolve().parent / "migration_phase4.sql"
    if not sql_file.exists():
        raise FileNotFoundError(f"Migration script not found: {sql_file}")

    migration_sql = sql_file.read_text(encoding="utf-8")

    async with db.engine.begin() as conn:
        logger.info("Executing Phase 4 migration SQL from %s...", sql_file.name)
        try:
            raw_conn = await conn.get_raw_connection()
            # asyncpg connection execute supports multi-statement script execution
            await raw_conn.driver_connection.execute(migration_sql)
        except Exception:
            await conn.execute(text(migration_sql))
        logger.info("Phase 4 migration applied successfully!")

    await manager.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
