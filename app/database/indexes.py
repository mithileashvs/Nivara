"""Database schema and index synchronization.

Idempotent — safe to run on every startup.
Ensures all 15 tables and indexes exist in PostgreSQL / SQLite.
"""
import logging
from typing import Any

logger = logging.getLogger("nivara.db")


async def ensure_indexes(db: Any) -> None:
    """Ensure all tables, constraints, and indexes exist in the target database."""
    if hasattr(db, "ensure_indexes"):
        await db.ensure_indexes()
    logger.info("Database tables and indexes ensured")
