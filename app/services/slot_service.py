"""Slot engine: generation, atomic state transitions, and bookable-slot queries.

CONCURRENCY MODEL
-----------------
The slot document is the single arbiter of who owns a time slot. Every state change is ONE
conditional atomic update (``find_one_and_update`` with the expected state in the filter):

* claim     : AVAILABLE                       -> HELD (patient request) / BOOKED (doctor reschedule)
* promote   : HELD by appt X, hold not expired -> BOOKED            (doctor accepts)
* release   : HELD|BOOKED by appt X           -> AVAILABLE|BLOCKED  (reject / cancel / reschedule)
* expire    : HELD and held_until < now       -> AVAILABLE|BLOCKED  (stale request)

MongoDB guarantees single-document atomicity, so when two patients race for the same slot exactly
one ``claim`` matches; the other gets ``None`` and a 409. No "check, then insert" gap exists, and
no multi-document transaction (which needs a replica set) is required.
"""
from datetime import date, datetime, timedelta
from typing import Any

from app.core.config import Settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.database.collections import C
from app.models.enums import AvailabilityStatus, SlotStatus
from app.models.scheduling import AppointmentSlot
from app.services.intake_service import IntakeService
from app.services.slot_rules import effective_status, slot_block_reason, REASON_MESSAGES
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate
from app.utils.time_utils import add_minutes, date_to_str, local_to_utc, minutes_between, parse_time, today_local, utcnow, parse_date

MAX_SLOT_SEARCH_DAYS = 31


class SlotService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.intake = IntakeService(db)

    @property
    def slots(self) -> Any:
        return self.db[C.APPOINTMENT_SLOTS]

    async def get(self, slot_id: str) -> dict:
        slot = await self.slots.find_one({"_id": slot_id})
        if slot is None:
            raise NotFoundError("Slot not found", code="slot_not_found")
        return slot

    # ------------------------------------------------------------------ atomic transitions

    async def claim(
        self,
        slot_id: str,
        appointment_id: str,
        *,
        target: SlotStatus,
        hold_until: datetime | None,
        now: datetime,
    ) -> dict:
        """Atomically take an AVAILABLE, sufficiently-future slot. Raises 409 if someone else got it."""
        earliest = now + timedelta(minutes=self.settings.min_booking_lead_minutes)
        doc = await self.slots.find_one_and_update(
            {"_id": slot_id, "status": SlotStatus.AVAILABLE, "start_at": {"$gte": earliest}},
            {
                "$set": {
                    "status": target,
                    "appointment_id": appointment_id,
                    "held_until": hold_until,
                    "block_source": None,
                    "blocked_by_availability_id": None,
                    "updated_at": now,
                }
            },
        )
        if doc is None:
            raise ConflictError(
                "This slot is no longer available. Please choose another slot.", code="slot_unavailable"
            )
        return doc

    async def promote_to_booked(self, slot_id: str, appointment_id: str, now: datetime) -> bool:
        doc = await self.slots.find_one_and_update(
            {"_id": slot_id, "appointment_id": appointment_id, "status": SlotStatus.HELD, "held_until": {"$gte": now}},
            {"$set": {"status": SlotStatus.BOOKED, "held_until": None, "updated_at": now}},
        )
        return doc is not None

    async def release(self, slot_id: str, appointment_id: str) -> dict | None:
        """Free a slot owned by ``appointment_id``. Returns the updated slot, or None if it was not owned
        by that appointment any more (already released / re-claimed) — releasing is idempotent."""
        slot = await self.slots.find_one({"_id": slot_id})
        if slot is None:
            return None
        return await self.slots.find_one_and_update(
            {"_id": slot_id, "appointment_id": appointment_id, "status": {"$in": [SlotStatus.HELD, SlotStatus.BOOKED]}},
            {"$set": await self._resting_fields(slot)},
        )

    async def release_expired_hold(self, slot: dict, now: datetime) -> dict | None:
        """Atomically release a HELD slot whose hold has expired. Returns the slot as it was BEFORE
        release (so the caller can find the appointment to expire), or None if not expired/held."""
        doc = await self.slots.find_one_and_update(
            {"_id": slot["_id"], "status": SlotStatus.HELD, "held_until": {"$lt": now}},
            {"$set": await self._resting_fields(slot)},
        )
        if doc is None:
            return None
        return slot

    async def _resting_fields(self, slot: dict) -> dict[str, Any]:
        """State a slot returns to once released: BLOCKED if a doctor time-off window now covers it
        (so a cancelled slot inside time-off does not reappear as bookable), otherwise AVAILABLE."""
        blocking = await self.db[C.DOCTOR_AVAILABILITY].find_one(
            {
                "doctor_id": slot["doctor_id"],
                "date": slot["date"],
                "status": AvailabilityStatus.BLOCKED,
                "start_time": {"$lt": slot["end_time"]},
                "end_time": {"$gt": slot["start_time"]},
            }
        )
        fields: dict[str, Any] = {
            "status": SlotStatus.BLOCKED if blocking else SlotStatus.AVAILABLE,
            "appointment_id": None,
            "held_until": None,
            "block_source": "AVAILABILITY" if blocking else None,
            "blocked_by_availability_id": blocking["_id"] if blocking else None,
            "updated_at": utcnow(),
        }
        return fields

    # ------------------------------------------------------------------ generation & blocking

    async def generate_from_window(self, availability: dict) -> int:
        """Materialise slots for a WORKING window. Idempotent: existing slots are never overwritten
        (unique index on doctor/date/start_time + upsert with $setOnInsert)."""
        start = parse_time(availability["start_time"])
        duration = availability["slot_duration"]
        count = minutes_between(start, parse_time(availability["end_time"])) // duration
        ops: list[tuple[dict, dict]] = []
        for i in range(count):
            st = add_minutes(start, i * duration)
            et = add_minutes(start, (i + 1) * duration)
            st_s, et_s = st.strftime("%H:%M"), et.strftime("%H:%M")
            doc = AppointmentSlot(
                doctor_id=availability["doctor_id"],
                hospital_id=availability["hospital_id"],
                department_id=availability["department_id"],
                date=availability["date"],
                start_time=st_s,
                end_time=et_s,
                start_at=local_to_utc(availability["date"], st_s, self.settings.app_timezone),
                end_at=local_to_utc(availability["date"], et_s, self.settings.app_timezone),
                availability_id=availability["_id"],
            ).to_mongo()
            key = {"doctor_id": doc.pop("doctor_id"), "date": doc.pop("date"), "start_time": doc.pop("start_time")}
            ops.append((key, {"$setOnInsert": doc}))
        if not ops:
            return 0
        created = 0
        for key, update in ops:  # idempotent per-slot upsert (max ~72 per window)
            res = await self.slots.update_one(key, update, upsert=True)
            created += 1 if res.upserted_id is not None else 0
        # Re-apply any time-off windows already defined for that day to the new slots.
        async for blocked in self.db[C.DOCTOR_AVAILABILITY].find(
            {"doctor_id": availability["doctor_id"], "date": availability["date"], "status": AvailabilityStatus.BLOCKED}
        ):
            await self.apply_block(blocked)
        return created

    async def apply_block(self, blocked: dict) -> tuple[int, int]:
        """Block FREE slots overlapping a time-off window. HELD/BOOKED slots are never touched —
        existing appointments remain valid. Returns ``(blocked_count, reserved_untouched)``."""
        overlap = {
            "doctor_id": blocked["doctor_id"],
            "date": blocked["date"],
            "start_time": {"$lt": blocked["end_time"]},
            "end_time": {"$gt": blocked["start_time"]},
        }
        res = await self.slots.update_many(
            {**overlap, "status": SlotStatus.AVAILABLE},
            {
                "$set": {
                    "status": SlotStatus.BLOCKED,
                    "block_source": "AVAILABILITY",
                    "blocked_by_availability_id": blocked["_id"],
                    "updated_at": utcnow(),
                }
            },
        )
        reserved = await self.slots.count_documents(
            {**overlap, "status": {"$in": [SlotStatus.HELD, SlotStatus.BOOKED]}}
        )
        return res.modified_count, reserved

    async def remove_block(self, availability_id: str) -> int:
        res = await self.slots.update_many(
            {"blocked_by_availability_id": availability_id, "status": SlotStatus.BLOCKED},
            {
                "$set": {
                    "status": SlotStatus.AVAILABLE,
                    "block_source": None,
                    "blocked_by_availability_id": None,
                    "updated_at": utcnow(),
                }
            },
        )
        return res.modified_count

    async def delete_window_slots(self, availability_id: str) -> int:
        """Delete the unreserved slots generated by a working window. Refuses if any are HELD/BOOKED."""
        reserved = await self.slots.count_documents(
            {"availability_id": availability_id, "status": {"$in": [SlotStatus.HELD, SlotStatus.BOOKED]}}
        )
        if reserved:
            raise ConflictError(
                f"{reserved} slot(s) in this window have pending or confirmed appointments. "
                "Resolve those appointments first.",
                code="window_has_reservations",
            )
        res = await self.slots.delete_many({"availability_id": availability_id})
        return res.deleted_count

    async def block_slot(self, doctor_id: str, slot_id: str) -> dict:
        now = utcnow()
        doc = await self.slots.find_one_and_update(
            {"_id": slot_id, "doctor_id": doctor_id, "status": SlotStatus.AVAILABLE},
            {"$set": {"status": SlotStatus.BLOCKED, "block_source": "MANUAL", "updated_at": now}},
        )
        if doc is None:
            await self._explain_missing(doctor_id, slot_id, "Only an AVAILABLE slot can be blocked.")
        return doc  # type: ignore[return-value]

    async def unblock_slot(self, doctor_id: str, slot_id: str) -> dict:
        now = utcnow()
        doc = await self.slots.find_one_and_update(
            {"_id": slot_id, "doctor_id": doctor_id, "status": SlotStatus.BLOCKED, "block_source": "MANUAL"},
            {"$set": {"status": SlotStatus.AVAILABLE, "block_source": None, "updated_at": now}},
        )
        if doc is None:
            await self._explain_missing(doctor_id, slot_id, "Only a manually blocked slot can be unblocked here.")
        return doc  # type: ignore[return-value]

    async def _explain_missing(self, doctor_id: str, slot_id: str, conflict_msg: str) -> None:
        slot = await self.slots.find_one({"_id": slot_id, "doctor_id": doctor_id}, {"_id": 1})
        if slot is None:
            raise NotFoundError("Slot not found", code="slot_not_found")  # also hides other doctors' slots
        raise ConflictError(conflict_msg, code="invalid_slot_state")

    # ------------------------------------------------------------------ queries / presentation

    def _resolve_dates(self, date_from: date | None, date_to: date | None, default_days: int = 14) -> tuple[str, str]:
        today = today_local(self.settings.app_timezone)
        start = max(date_from or today, today)
        end = date_to or (start + timedelta(days=default_days))
        if end < start:
            raise BadRequestError("date_to must be on or after date_from", code="invalid_date_range")
        if (end - start).days > MAX_SLOT_SEARCH_DAYS:
            raise BadRequestError(
                f"Date range may not exceed {MAX_SLOT_SEARCH_DAYS} days", code="invalid_date_range"
            )
        return date_to_str(start), date_to_str(end)

    async def search_for_patients(
        self,
        *,
        doctor_id: str,
        date_from: date | None,
        date_to: date | None,
        hospital_id: str | None,
        department_id: str | None,
        include_unavailable: bool,
        params: PageParams,
    ) -> tuple[list[dict], int]:
        doctor = await self.db[C.DOCTORS].find_one({"_id": oid(doctor_id), "profile_status": "ACTIVE"})
        if doctor is None:
            raise NotFoundError("Doctor not found", code="doctor_not_found")
        start, end = self._resolve_dates(date_from, date_to)
        now = utcnow()
        query: dict[str, Any] = {"doctor_id": doctor["_id"], "date": {"$gte": start, "$lte": end}}

        if include_unavailable:
            if hospital_id:
                query["hospital_id"] = oid(hospital_id)
            if department_id:
                query["department_id"] = oid(department_id)
        else:
            # Only genuinely bookable slots: facility intake is resolved into the query itself so
            # pagination totals stay correct and closed hospitals/departments never appear bookable.
            open_h, open_d = await self.intake.open_scope(
                hospital_ids=doctor.get("hospital_ids", []), department_ids=doctor.get("department_ids", [])
            )
            if hospital_id:
                open_h = [h for h in open_h if h == oid(hospital_id)]
            if department_id:
                open_d = [d for d in open_d if d == oid(department_id)]
            if doctor.get("availability_status") != "OPEN" or not open_h or not open_d:
                return [], 0
            query["hospital_id"] = {"$in": open_h}
            query["department_id"] = {"$in": open_d}
            query["start_at"] = {"$gte": now + timedelta(minutes=self.settings.min_booking_lead_minutes)}
            query["$or"] = [
                {"status": SlotStatus.AVAILABLE},
                {"status": SlotStatus.HELD, "held_until": {"$lt": now}},
            ]

        docs, total = await paginate(self.slots, query, params, sort=[("start_at", 1)])
        return await self._present(docs, {doctor["_id"]: doctor}, now), total

    async def list_for_doctor(
        self,
        doctor: dict,
        *,
        date_from: date | None,
        date_to: date | None,
        status: SlotStatus | None,
        params: PageParams,
    ) -> tuple[list[dict], int]:
        start, end = self._resolve_dates(date_from, date_to)
        query: dict[str, Any] = {"doctor_id": doctor["_id"], "date": {"$gte": start, "$lte": end}}
        if status is not None:
            query["status"] = status
        docs, total = await paginate(self.slots, query, params, sort=[("start_at", 1)])
        return await self._present(docs, {doctor["_id"]: doctor}, utcnow(), detailed=True), total

    async def _present(
        self, slots: list[dict], doctors: dict[str, dict], now: datetime, detailed: bool = False
    ) -> list[dict]:
        hospitals, departments = await self.intake.load_context(
            {s["hospital_id"] for s in slots}, {s["department_id"] for s in slots}
        )
        out = []
        for s in slots:
            reason = slot_block_reason(
                s,
                doctors.get(s["doctor_id"]),
                hospitals.get(s["hospital_id"]),
                departments.get(s["department_id"]),
                now=now,
                min_lead_minutes=self.settings.min_booking_lead_minutes,
            )
            view = {
                "_id": s["_id"],
                "doctor_id": s["doctor_id"],
                "hospital_id": s["hospital_id"],
                "department_id": s["department_id"],
                "date": s["date"],
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "status": effective_status(s, now),
                "bookable": reason is None,
                "unavailable_reason": reason,
            }
            if detailed:
                view.update(
                    appointment_id=s.get("appointment_id"),
                    held_until=s.get("held_until"),
                    block_source=s.get("block_source"),
                )
            out.append(view)
        return out


def reason_to_error(reason: str) -> ConflictError:
    """Translate a bookability reason code into a 409 with a stable, lower-case error code."""
    return ConflictError(REASON_MESSAGES.get(reason, "This slot cannot be booked."), code=reason.lower())
