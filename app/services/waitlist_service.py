"""Smart waitlist: stores patient preferences and matches them against freed-up slots.

MATCHING ALGORITHM (see README):
1. Pre-filter waitlist entries in MongoDB: ACTIVE, date range covers the slot, not already notified
   for this slot, and every constraint the entry *specifies* is compatible with the slot.
2. Evaluate each candidate in Python. An entry is ELIGIBLE only if every specified criterion
   (doctor, hospital, department, specialty, date, time window, consultation type, "earlier than my
   existing appointment") is satisfied. Each satisfied criterion adds its configured weight, plus a
   capped bonus for time spent waiting — every point is listed in ``match_factors``.
3. Keep the best entry per patient, rank by score then by who has waited longest, notify the top N.
Nothing is booked automatically: the notified patient must submit a normal appointment request,
which the doctor then accepts or rejects.
"""
import logging
from datetime import date, datetime
from typing import Any

from app.core.config import MatchingConfig, Settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.database.collections import C
from app.models.engagement import WaitlistEntry
from app.models.enums import ACTIVE_APPOINTMENT_STATUSES, NotificationType, WaitlistStatus
from app.schemas.engagement import WaitlistCreate
from app.services.notification_service import NotificationService
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate
from app.utils.text import normalize
from app.utils.time_utils import date_to_str, time_to_str, today_local, utcnow

logger = logging.getLogger("nivara.waitlist")


def evaluate_entry(
    entry: dict, slot: dict, doctor: dict, existing_start_at: datetime | None, cfg: MatchingConfig, now: datetime
) -> dict[str, Any] | None:
    """Return ``{"score", "factors"}`` if the entry is eligible for the slot, else None."""
    w = cfg.waitlist_weights
    score, factors = 0.0, []

    def hit(key: str, label: str) -> None:
        nonlocal score
        score += w.get(key, 0.0)
        factors.append(label)

    if entry.get("doctor_id"):
        if entry["doctor_id"] != slot["doctor_id"]:
            return None
        hit("doctor", "Preferred doctor")
    if entry.get("hospital_id"):
        if entry["hospital_id"] != slot["hospital_id"]:
            return None
        hit("hospital", "Preferred hospital")
    if entry.get("department_id"):
        if entry["department_id"] != slot["department_id"]:
            return None
        hit("department", "Preferred department")
    if entry.get("specialty_normalized"):
        if entry["specialty_normalized"] != doctor.get("specialty_normalized"):
            return None
        hit("specialty", "Specialty match")
    if not (entry["date_from"] <= slot["date"] <= entry["date_to"]):
        return None
    if entry.get("time_from") or entry.get("time_to"):
        if entry.get("time_from") and slot["start_time"] < entry["time_from"]:
            return None
        if entry.get("time_to") and slot["start_time"] >= entry["time_to"]:
            return None
        hit("time_window", "Within preferred time range")
    if entry.get("consultation_type"):
        if entry["consultation_type"] not in doctor.get("consultation_types", []):
            return None
        hit("consultation_type", "Consultation type offered")
    if entry.get("existing_appointment_id"):
        if existing_start_at is None or slot["start_at"] >= existing_start_at:
            return None
        hit("earlier_than_existing", "Earlier than your current appointment")
    waited = max(0, (now - entry["created_at"]).days)
    if waited:
        cap = cfg.waiting_time_cap_days
        score += w.get("waiting_time", 0.0) * min(waited, cap) / cap
        factors.append(f"Waiting {waited} day(s)")
    return {"score": round(score, 2), "factors": factors}


class WaitlistService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.notifications = NotificationService(db)

    @property
    def coll(self) -> Any:
        return self.db[C.WAITLIST_ENTRIES]

    # ------------------------------------------------------------------ patient-facing

    async def create(self, patient: dict, payload: WaitlistCreate) -> dict:
        today = today_local(self.settings.app_timezone)
        if payload.date_to < today:
            raise BadRequestError("date_to is in the past", code="date_in_past")
        if payload.doctor_id and not await self.db[C.DOCTORS].find_one({"_id": oid(payload.doctor_id), "profile_status": "ACTIVE"}, {"_id": 1}):
            raise NotFoundError("Doctor not found", code="doctor_not_found")
        if payload.hospital_id and not await self.db[C.HOSPITALS].find_one({"_id": oid(payload.hospital_id)}, {"_id": 1}):
            raise NotFoundError("Hospital not found", code="hospital_not_found")
        if payload.department_id and not await self.db[C.DEPARTMENTS].find_one({"_id": oid(payload.department_id)}, {"_id": 1}):
            raise NotFoundError("Department not found", code="department_not_found")
        existing_id = None
        if payload.existing_appointment_id:
            existing = await self.db[C.APPOINTMENTS].find_one(
                {"_id": oid(payload.existing_appointment_id), "patient_id": patient["_id"], "status": {"$in": list(ACTIVE_APPOINTMENT_STATUSES)}}
            )
            if existing is None:
                raise BadRequestError("existing_appointment_id must be one of your active appointments", code="invalid_existing_appointment")
            existing_id = existing["_id"]
        active = await self.coll.count_documents({"patient_id": patient["_id"], "status": WaitlistStatus.ACTIVE})
        if active >= self.settings.waitlist_max_active_entries_per_patient:
            raise ConflictError("Too many active waitlist entries. Cancel one first.", code="waitlist_limit_reached")

        doc = WaitlistEntry(
            patient_id=patient["_id"],
            patient_user_id=patient["user_id"],
            doctor_id=oid(payload.doctor_id) if payload.doctor_id else None,
            department_id=oid(payload.department_id) if payload.department_id else None,
            hospital_id=oid(payload.hospital_id) if payload.hospital_id else None,
            specialty=payload.specialty,
            date_from=date_to_str(payload.date_from),
            date_to=date_to_str(payload.date_to),
            time_from=time_to_str(payload.time_from) if payload.time_from else None,
            time_to=time_to_str(payload.time_to) if payload.time_to else None,
            consultation_type=payload.consultation_type.value if payload.consultation_type else None,
            existing_appointment_id=existing_id,
        ).to_mongo()
        await self.coll.insert_one(doc)
        return doc

    async def list_mine(self, patient_id: str, params: PageParams, status: WaitlistStatus | None) -> tuple[list[dict], int]:
        query: dict[str, Any] = {"patient_id": patient_id}
        if status:
            query["status"] = status.value
        return await paginate(self.coll, query, params, sort=[("created_at", -1)])

    async def get_mine(self, patient_id: str, entry_id: str) -> dict:
        doc = await self.coll.find_one({"_id": oid(entry_id), "patient_id": patient_id})
        if doc is None:
            raise NotFoundError("Waitlist entry not found", code="waitlist_not_found")
        return doc

    async def cancel(self, patient_id: str, entry_id: str) -> dict:
        doc = await self.coll.find_one_and_update(
            {"_id": oid(entry_id), "patient_id": patient_id, "status": WaitlistStatus.ACTIVE},
            {"$set": {"status": WaitlistStatus.CANCELLED, "updated_at": utcnow()}},
        )
        if doc is None:
            await self.get_mine(patient_id, entry_id)  # 404 if not theirs
            raise ConflictError("Only ACTIVE waitlist entries can be cancelled", code="waitlist_not_active")
        return doc

    async def mark_fulfilled(self, patient_id: str, slot_id: str, appointment_id: str) -> int:
        """A patient who requests a slot they were notified about has had their entry satisfied."""
        res = await self.coll.update_many(
            {"patient_id": patient_id, "status": WaitlistStatus.ACTIVE, "notified_slot_ids": slot_id},
            {"$set": {"status": WaitlistStatus.FULFILLED, "fulfilled_appointment_id": appointment_id, "updated_at": utcnow()}},
        )
        return res.modified_count

    async def expire_old(self) -> int:
        today = date_to_str(today_local(self.settings.app_timezone))
        res = await self.coll.update_many(
            {"status": WaitlistStatus.ACTIVE, "date_to": {"$lt": today}},
            {"$set": {"status": WaitlistStatus.EXPIRED, "updated_at": utcnow()}},
        )
        return res.modified_count

    # ------------------------------------------------------------------ matching

    async def find_eligible(self, slot: dict, doctor: dict, exclude_patient_id: str | None = None) -> list[dict[str, Any]]:
        now = utcnow()
        conds: list[dict[str, Any]] = [
            {"status": WaitlistStatus.ACTIVE},
            {"date_from": {"$lte": slot["date"]}},
            {"date_to": {"$gte": slot["date"]}},
            {"notified_slot_ids": {"$ne": slot["_id"]}},
            {"$or": [{"doctor_id": None}, {"doctor_id": slot["doctor_id"]}]},
            {"$or": [{"hospital_id": None}, {"hospital_id": slot["hospital_id"]}]},
            {"$or": [{"department_id": None}, {"department_id": slot["department_id"]}]},
            {"$or": [{"specialty_normalized": None}, {"specialty_normalized": doctor.get("specialty_normalized")}]},
        ]
        if exclude_patient_id:
            conds.append({"patient_id": {"$ne": exclude_patient_id}})
        candidates = await self.coll.find({"$and": conds}).sort("created_at", 1).limit(500).to_list(length=500)

        existing_ids = [c["existing_appointment_id"] for c in candidates if c.get("existing_appointment_id")]
        existing_start: dict[str, datetime] = {}
        if existing_ids:
            async for a in self.db[C.APPOINTMENTS].find(
                {"_id": {"$in": existing_ids}, "is_active": True}, {"start_at": 1}
            ):
                existing_start[str(a["_id"])] = a["start_at"]

        best: dict[str, dict[str, Any]] = {}
        for entry in candidates:
            result = evaluate_entry(
                entry, slot, doctor, existing_start.get(str(entry.get("existing_appointment_id"))), self.settings.matching_config, now
            )
            if result is None:
                continue
            row = {"entry": entry, **result}
            current = best.get(str(entry["patient_id"]))
            if current is None or row["score"] > current["score"]:
                best[str(entry["patient_id"])] = row
        return sorted(best.values(), key=lambda r: (-r["score"], r["entry"]["created_at"]))

    async def notify_for_slot(self, slot: dict, doctor: dict, exclude_patient_id: Any = None) -> list[dict[str, Any]]:
        ranked = await self.find_eligible(slot, doctor, exclude_patient_id)
        notified: list[dict[str, Any]] = []
        for row in ranked[: self.settings.waitlist_notify_top_n]:
            entry = row["entry"]
            # Atomic claim of the (entry, slot) pair so concurrent recoveries never double-notify.
            claimed = await self.coll.find_one_and_update(
                {"_id": entry["_id"], "status": WaitlistStatus.ACTIVE, "notified_slot_ids": {"$ne": slot["_id"]}},
                {"$addToSet": {"notified_slot_ids": slot["_id"]}, "$set": {"updated_at": utcnow()}},
            )
            if claimed is None:
                continue
            await self.notifications.notify(
                user_id=entry["patient_user_id"],
                type=NotificationType.WAITLIST_SLOT_AVAILABLE,
                title="An appointment slot has opened up",
                message=(
                    f"Dr. {doctor['name']} ({doctor['specialty']}) has a slot on {slot['date']} at {slot['start_time']}. "
                    "Request it now to secure it — slots are first come, first served and the doctor must confirm."
                ),
                data={
                    "slot_id": str(slot["_id"]), "doctor_id": str(slot["doctor_id"]), "hospital_id": str(slot["hospital_id"]),
                    "department_id": str(slot["department_id"]), "date": slot["date"], "start_time": slot["start_time"],
                    "waitlist_entry_id": str(entry["_id"]), "match_score": row["score"], "match_factors": row["factors"],
                },
            )
            notified.append({"patient_id": entry["patient_id"], "entry_id": entry["_id"], "score": row["score"], "factors": row["factors"]})
        return notified
