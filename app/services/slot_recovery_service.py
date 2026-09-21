"""Cancelled-slot recovery: when a booked/held slot becomes free again, offer it to the waitlist."""
import logging
from typing import Any

from app.core.config import Settings
from app.database.collections import C
from app.services.slot_rules import slot_block_reason
from app.services.waitlist_service import WaitlistService
from app.utils.time_utils import utcnow

logger = logging.getLogger("nivara.recovery")


class SlotRecoveryService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.waitlist = WaitlistService(db, settings)

    async def on_slot_released(self, slot_id: Any, *, exclude_patient_id: Any = None) -> list[dict]:
        """Re-check the freed slot against ALL bookability rules (slot status, doctor, hospital and
        department intake, lead time) and only then look for waitlist matches. Never raises."""
        try:
            slot = await self.db[C.APPOINTMENT_SLOTS].find_one({"_id": str(slot_id)})
            if slot is None or slot["status"] != "AVAILABLE":
                return []  # re-claimed already, or blocked by doctor time-off
            doctor = await self.db[C.DOCTORS].find_one({"_id": slot["doctor_id"]})
            hospital = await self.db[C.HOSPITALS].find_one({"_id": slot["hospital_id"]})
            department = await self.db[C.DEPARTMENTS].find_one({"_id": slot["department_id"]})
            reason = slot_block_reason(
                slot, doctor, hospital, department, now=utcnow(), min_lead_minutes=self.settings.min_booking_lead_minutes
            )
            if reason:
                logger.info("Recovered slot %s not offered to waitlist: %s", slot_id, reason)
                return []
            return await self.waitlist.notify_for_slot(slot, doctor, exclude_patient_id)
        except Exception:  # noqa: BLE001
            logger.exception("Slot recovery failed for slot %s", slot_id)
            return []
