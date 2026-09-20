"""Periodic housekeeping: expire stale requests, send reminders, expire old waitlist entries."""
import logging
from datetime import timedelta
from typing import Any

from app.core.config import Settings
from app.database.collections import C
from app.models.enums import AppointmentStatus, NotificationType, SlotStatus
from app.services.appointment_service import AppointmentService
from app.services.notification_service import NotificationService
from app.services.waitlist_service import WaitlistService
from app.utils.time_utils import utcnow

logger = logging.getLogger("smartcare.maintenance")
BATCH = 200


class MaintenanceService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.appointments = AppointmentService(db, settings)
        self.notifications = NotificationService(db)
        self.waitlist = WaitlistService(db, settings)

    async def expire_stale_holds(self) -> int:
        now = utcnow()
        stale = await self.db[C.APPOINTMENT_SLOTS].find(
            {"status": SlotStatus.HELD, "held_until": {"$lt": now}}
        ).limit(BATCH).to_list(length=BATCH)
        expired = 0
        for slot in stale:
            try:
                expired += 1 if await self.appointments.expire_stale_hold(slot) else 0
            except Exception:  # noqa: BLE001
                logger.exception("Failed to expire hold on slot %s", slot["_id"])
        return expired

    async def send_due_reminders(self) -> int:
        now = utcnow()
        due = self.db[C.APPOINTMENTS].find(
            {"status": AppointmentStatus.CONFIRMED, "reminder_sent": False, "start_at": {"$gt": now, "$lte": now + timedelta(hours=self.settings.reminder_hours_before)}}
        ).limit(BATCH)
        sent = 0
        async for appt in due:
            # Atomic flag flip => each reminder is sent once even with several workers.
            claimed = await self.db[C.APPOINTMENTS].find_one_and_update(
                {"_id": appt["_id"], "reminder_sent": False, "status": AppointmentStatus.CONFIRMED}, {"$set": {"reminder_sent": True}}
            )
            if claimed is None:
                continue
            await self.notifications.notify(
                user_id=appt["patient_user_id"], type=NotificationType.APPOINTMENT_REMINDER, title="Appointment reminder",
                message=f"Reminder: you have an appointment with Dr. {appt['doctor_name']} on {appt['appointment_date']} at {appt['start_time']}.",
                appointment_id=appt["_id"],
            )
            sent += 1
        return sent

    async def run_all(self) -> dict[str, int]:
        return {
            "expired_holds": await self.expire_stale_holds(),
            "reminders_sent": await self.send_due_reminders(),
            "waitlist_entries_expired": await self.waitlist.expire_old(),
        }
