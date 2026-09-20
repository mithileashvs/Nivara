"""Doctor working hours / time-off management and slot generation."""
from datetime import timedelta
from typing import Any

from bson import ObjectId

from app.core.config import Settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.database.collections import C
from app.models.enums import AvailabilityStatus, ProfileStatus
from app.models.scheduling import DoctorAvailability
from app.schemas.scheduling import AvailabilityCreate
from app.services.slot_service import SlotService
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate
from app.utils.time_utils import date_to_str, minutes_between, time_to_str, today_local


class AvailabilityService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.slots = SlotService(db, settings)

    @property
    def coll(self) -> Any:
        return self.db[C.DOCTOR_AVAILABILITY]

    async def create(self, doctor: dict, payload: AvailabilityCreate) -> dict[str, Any]:
        if doctor["profile_status"] != ProfileStatus.ACTIVE:
            raise ConflictError(
                "Your doctor profile must be verified by an administrator before you can publish availability.",
                code="doctor_not_active",
            )
        today = today_local(self.settings.app_timezone)
        if payload.date < today:
            raise BadRequestError("Availability cannot be created for a past date", code="date_in_past")
        if payload.date > today + timedelta(days=self.settings.max_scheduling_horizon_days):
            raise BadRequestError(
                f"Availability can only be created up to {self.settings.max_scheduling_horizon_days} days ahead",
                code="date_too_far",
            )

        hospital_id, department_id = oid(payload.hospital_id), oid(payload.department_id)
        department = await self.db[C.DEPARTMENTS].find_one({"_id": department_id, "hospital_id": hospital_id})
        if department is None:
            raise NotFoundError("Department not found in that hospital", code="department_not_found")
        if hospital_id not in doctor.get("hospital_ids", []) or department_id not in doctor.get("department_ids", []):
            raise BadRequestError(
                "You are not affiliated with that hospital/department. Ask an administrator to update your affiliations.",
                code="not_affiliated",
            )

        start_s, end_s = time_to_str(payload.start_time), time_to_str(payload.end_time)
        if payload.status == AvailabilityStatus.WORKING:
            if minutes_between(payload.start_time, payload.end_time) < payload.slot_duration:
                raise BadRequestError("Window is shorter than one slot", code="window_too_short")

        # No overlapping windows of the same kind for the same doctor/day.
        overlap = await self.coll.find_one(
            {
                "doctor_id": doctor["_id"],
                "date": date_to_str(payload.date),
                "status": payload.status,
                "start_time": {"$lt": end_s},
                "end_time": {"$gt": start_s},
            }
        )
        if overlap is not None:
            raise ConflictError(
                f"Overlaps an existing {payload.status.lower()} window ({overlap['start_time']}-{overlap['end_time']})",
                code="availability_overlap",
            )

        doc = DoctorAvailability(
            doctor_id=doctor["_id"],
            hospital_id=hospital_id,
            department_id=department_id,
            date=date_to_str(payload.date),
            start_time=start_s,
            end_time=end_s,
            slot_duration=payload.slot_duration,
            status=payload.status,
            note=payload.note,
        ).to_mongo()
        await self.coll.insert_one(doc)

        result = {**doc, "slots_created": 0, "slots_blocked": 0, "reserved_slots_unaffected": 0}
        if payload.status == AvailabilityStatus.WORKING:
            result["slots_created"] = await self.slots.generate_from_window(doc)
        else:
            result["slots_blocked"], result["reserved_slots_unaffected"] = await self.slots.apply_block(doc)
        return result

    async def list_for_doctor(
        self, doctor_id: ObjectId, params: PageParams, date_from: str | None, date_to: str | None
    ) -> tuple[list[dict], int]:
        query: dict[str, Any] = {"doctor_id": doctor_id}
        if date_from or date_to:
            query["date"] = {}
            if date_from:
                query["date"]["$gte"] = date_from
            if date_to:
                query["date"]["$lte"] = date_to
        return await paginate(self.coll, query, params, sort=[("date", 1), ("start_time", 1)])

    async def delete(self, doctor_id: ObjectId, availability_id: str) -> dict[str, int]:
        window = await self.coll.find_one({"_id": oid(availability_id), "doctor_id": doctor_id})
        if window is None:
            raise NotFoundError("Availability not found", code="availability_not_found")
        if window["status"] == AvailabilityStatus.WORKING:
            removed = await self.slots.delete_window_slots(window["_id"])  # 409 if reservations exist
            await self.coll.delete_one({"_id": window["_id"]})
            return {"slots_removed": removed, "slots_unblocked": 0}
        unblocked = await self.slots.remove_block(window["_id"])
        await self.coll.delete_one({"_id": window["_id"]})
        return {"slots_removed": 0, "slots_unblocked": unblocked}
