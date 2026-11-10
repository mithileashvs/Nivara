"""Cancelled-slot recovery: when a booked/held slot becomes free again, offer it to the waitlist."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.core.config import Settings
from app.database.collections import C
from app.database.session import _normalize_row
from app.database.tables import (
    appointment_slots_table as st,
    departments_table as dept_t,
    doctors_table as dt,
    hospitals_table as ht_hosp,
)
from app.services.slot_rules import slot_block_reason
from app.services.waitlist_service import WaitlistService
from app.utils.time_utils import utcnow

logger = logging.getLogger("nivara.recovery")


class SlotRecoveryService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.waitlist = WaitlistService(db, settings)

    async def _fetch_one(self, stmt: Any, table_name: str) -> dict[str, Any] | None:
        if getattr(self.db, "_conn", None) is not None:
            res = await self.db._conn.execute(stmt)
            row = res.mappings().first()
            return _normalize_row(dict(row), table_name) if row else None
        async with self.db.connect() as conn:
            res = await conn.execute(stmt)
            row = res.mappings().first()
            return _normalize_row(dict(row), table_name) if row else None

    async def on_slot_released(self, slot_id: Any, *, exclude_patient_id: Any = None) -> list[dict]:
        """Re-check the freed slot against ALL bookability rules (slot status, doctor, hospital and
        department intake, lead time) and only then look for waitlist matches. Never raises."""
        try:
            slot_stmt = select(st).where(st.c.id == str(slot_id))
            slot = await self._fetch_one(slot_stmt, C.APPOINTMENT_SLOTS)
            if slot is None or slot["status"] != "AVAILABLE":
                return []  # re-claimed already, or blocked by doctor time-off

            doc_stmt = select(dt).where(dt.c.id == str(slot["doctor_id"]))
            doctor = await self._fetch_one(doc_stmt, C.DOCTORS)

            hosp_stmt = select(ht_hosp).where(ht_hosp.c.id == str(slot["hospital_id"]))
            hospital = await self._fetch_one(hosp_stmt, C.HOSPITALS)

            dept_stmt = select(dept_t).where(dept_t.c.id == str(slot["department_id"]))
            department = await self._fetch_one(dept_stmt, C.DEPARTMENTS)

            reason = slot_block_reason(
                slot, doctor, hospital, department, now=utcnow(), min_lead_minutes=self.settings.min_booking_lead_minutes
            )
            if reason:
                logger.info("Recovered slot %s not offered to waitlist: %s", slot_id, reason)
                return []
            res = await self.waitlist.process_slot_for_waitlist(slot, doctor, exclude_patient_id)
            return [res] if res else []
        except Exception:  # noqa: BLE001
            logger.exception("Slot recovery failed for slot %s", slot_id)
            return []
