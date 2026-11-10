"""Nivara Phase 5 Migration Runner

Applies performance-justified analytical B-tree indexes:
- ix_appointments_hospital_date_status ON appointments (hospital_id, appointment_date, status)
- ix_appointments_department_date_status ON appointments (department_id, appointment_date, status)
- ix_patients_created_at ON patients (created_at)
- ix_slots_hospital_date_status ON appointment_slots (hospital_id, date, status)
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
logger = logging.getLogger("nivara.migration_phase5")


async def run_migration() -> None:
    settings = get_settings()
    manager = DatabaseManager(settings)
    logger.info("Connecting to database: %s", settings.database_name)
    try:
        db = await manager.connect()
    except Exception as exc:
        logger.error("Failed to connect to database: %s", exc)
        logger.info("You can run scripts/migration_phase5.sql directly in the Supabase SQL Editor.")
        return

    sql_file = Path(__file__).resolve().parent / "migration_phase5.sql"
    if not sql_file.exists():
        raise FileNotFoundError(f"Migration script not found: {sql_file}")

    migration_sql = sql_file.read_text(encoding="utf-8")

    async with db.engine.begin() as conn:
        logger.info("Executing Phase 5 migration SQL from %s...", sql_file.name)
        try:
            raw_conn = await conn.get_raw_connection()
            await raw_conn.driver_connection.execute(migration_sql)
        except Exception:
            await conn.execute(text(migration_sql))
        logger.info("Phase 5 migration applied successfully!")

    await manager.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
