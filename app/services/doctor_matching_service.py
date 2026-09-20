"""Appointment discovery: transparent, configurable doctor/slot matching.

This finds *appointments that can actually be booked* that fit a person's stated preferences. It is
NOT a medical recommendation: it never considers symptoms, conditions, or clinical suitability.

Only doctors with at least one genuinely bookable slot are returned (doctor ACTIVE + intake OPEN,
hospital OPEN, department ACTIVE + OPEN, slot free and in the future).

Scoring: every applicable factor contributes ``weight * achieved`` (achieved in 0..1). The final
score is ``100 * earned / max_applicable`` and every component is returned in ``score_breakdown``.
Weights come from ``Settings.matching_config`` (env ``MATCHING_CONFIG``) — no hidden constants.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from bson import ObjectId

from app.core.config import Settings
from app.core.errors import BadRequestError
from app.database.collections import C
from app.models.enums import SlotStatus
from app.schemas.smart import MatchCriteria
from app.services.doctor_service import DoctorService
from app.services.intake_service import IntakeService
from app.utils.geo import haversine_km
from app.utils.text import normalize
from app.utils.time_utils import date_to_str, time_to_str, today_local, utcnow

MAX_RANGE_DAYS = 60
SLOTS_PER_DOCTOR = 10


@dataclass
class Gathered:
    doctors: list[dict]
    slots_by_doctor: dict[ObjectId, list[dict]]
    hospitals: dict[ObjectId, dict]
    departments: dict[ObjectId, dict]
    date_from: str
    date_to: str
    now: datetime
    today: date


@dataclass
class Scored:
    score: float
    components: list[dict[str, Any]] = field(default_factory=list)
    factors: list[str] = field(default_factory=list)


def _in_window(start_time: str, t_from: str | None, t_to: str | None) -> bool:
    return (t_from is None or start_time >= t_from) and (t_to is None or start_time < t_to)


def _relative_when(slot: dict, today: date) -> str:
    slot_date = date.fromisoformat(slot["date"])
    diff = (slot_date - today).days
    day = "today" if diff == 0 else "tomorrow" if diff == 1 else f"on {slot['date']}"
    hour = int(slot["start_time"][:2])
    part = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    return f"{day} {part}"


def slot_option(slot: dict) -> dict[str, Any]:
    return {
        "slot_id": str(slot["_id"]), "doctor_id": str(slot["doctor_id"]), "hospital_id": str(slot["hospital_id"]),
        "department_id": str(slot["department_id"]), "date": slot["date"], "start_time": slot["start_time"], "end_time": slot["end_time"],
    }


class DoctorMatchingService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.doctors = DoctorService(db, settings)
        self.intake = IntakeService(db)

    # ------------------------------------------------------------------ data gathering

    def _resolve_range(self, c: MatchCriteria) -> tuple[date, date]:
        today = today_local(self.settings.app_timezone)
        start = max(c.date_from or today, today)
        end = c.date_to or start + timedelta(days=self.settings.matching_config.availability_horizon_days)
        if end < start or (end - start).days > MAX_RANGE_DAYS:
            raise BadRequestError(f"Invalid date range (must be ordered, max {MAX_RANGE_DAYS} days)", code="invalid_date_range")
        return start, end

    async def gather(self, c: MatchCriteria) -> Gathered:
        if (c.latitude is None) != (c.longitude is None):
            raise BadRequestError("latitude and longitude must be provided together", code="invalid_location")
        if c.max_distance_km is not None and c.latitude is None:
            raise BadRequestError("max_distance_km requires latitude and longitude", code="invalid_location")
        if c.preferred_time_from and c.preferred_time_to and c.preferred_time_to <= c.preferred_time_from:
            raise BadRequestError("preferred_time_to must be after preferred_time_from", code="invalid_time_range")
        cfg = self.settings.matching_config
        start, end = self._resolve_range(c)
        now, today = utcnow(), today_local(self.settings.app_timezone)

        query = await self.doctors.build_query(
            doctor_id=c.doctor_id, specialty=c.specialty, department_id=c.department_id, hospital_id=c.hospital_id,
            consultation_type=c.consultation_type.value if c.consultation_type else None,
            lat=c.latitude, lon=c.longitude, max_km=c.max_distance_km, only_open=True,
        )
        doctors = await self.db[C.DOCTORS].find(query).limit(cfg.max_candidate_doctors).to_list(length=cfg.max_candidate_doctors)
        empty = Gathered([], {}, {}, {}, date_to_str(start), date_to_str(end), now, today)
        if not doctors:
            return empty

        open_h, open_d = await self.intake.open_scope(
            hospital_ids=list({h for d in doctors for h in d.get("hospital_ids", [])}),
            department_ids=list({x for d in doctors for x in d.get("department_ids", [])}),
        )
        if c.hospital_id:
            open_h = [h for h in open_h if str(h) == c.hospital_id]
        if c.department_id:
            open_d = [d for d in open_d if str(d) == c.department_id]
        if not open_h or not open_d:
            return empty

        rows = await self.db[C.APPOINTMENT_SLOTS].aggregate([
            {"$match": {
                "doctor_id": {"$in": [d["_id"] for d in doctors]}, "hospital_id": {"$in": open_h}, "department_id": {"$in": open_d},
                "date": {"$gte": date_to_str(start), "$lte": date_to_str(end)},
                "start_at": {"$gte": now + timedelta(minutes=self.settings.min_booking_lead_minutes)},
                "$or": [{"status": SlotStatus.AVAILABLE}, {"status": SlotStatus.HELD, "held_until": {"$lt": now}}],
            }},
            {"$sort": {"start_at": 1}},
            {"$group": {"_id": "$doctor_id", "slots": {"$push": {
                "_id": "$_id", "doctor_id": "$doctor_id", "hospital_id": "$hospital_id", "department_id": "$department_id",
                "date": "$date", "start_time": "$start_time", "end_time": "$end_time", "start_at": "$start_at"}}}},
        ]).to_list(length=None)
        by_doctor = {r["_id"]: r["slots"] for r in rows}
        doctors = [d for d in doctors if d["_id"] in by_doctor]
        hospitals, departments = await self.intake.load_context(
            {s["hospital_id"] for ss in by_doctor.values() for s in ss}, {s["department_id"] for ss in by_doctor.values() for s in ss}
        )
        return Gathered(doctors, by_doctor, hospitals, departments, date_to_str(start), date_to_str(end), now, today)

    # ------------------------------------------------------------------ scoring

    def score(self, g: Gathered, doctor: dict, slots: list[dict], c: MatchCriteria, *, include_depth: bool = True) -> Scored:
        cfg = self.settings.matching_config
        w = cfg.weights
        comps: list[dict[str, Any]] = []
        factors: list[str] = []

        def add(name: str, achieved: float, detail: str, label: str | None = None) -> None:
            weight = w.get(name, 0.0)
            if weight <= 0:
                return
            achieved = max(0.0, min(1.0, achieved))
            comps.append({"factor": name, "weight": weight, "achieved": round(achieved, 3), "points": round(weight * achieved, 3), "detail": detail})
            if achieved > 0 and label:
                factors.append(label)

        if c.specialty:
            want, have = normalize(c.specialty), doctor.get("specialty_normalized", "")
            exact = want == have
            add("specialty", 1.0 if exact else 0.6, "Exact specialty match" if exact else f"Specialty '{doctor['specialty']}' starts with '{c.specialty}'",
                "Specialty match" if exact else "Specialty partially matches")
        if c.department_id:
            add("department", 1.0, "Slots in the requested department", "Department match")
        slot_hospitals = {s["hospital_id"] for s in slots}
        prefs = {ObjectId(h) for h in c.preferred_hospital_ids} | ({ObjectId(c.hospital_id)} if c.hospital_id else set())
        if prefs:
            hit = bool(slot_hospitals & prefs)
            add("hospital_preference", 1.0 if hit else 0.0, "Available at a preferred hospital" if hit else "Not at a preferred hospital", "Preferred hospital")
        if c.consultation_type:
            add("consultation_type", 1.0, f"Offers {c.consultation_type.value} consultations", f"Offers {c.consultation_type.value} appointments")

        first = min(slots, key=lambda s: s["start_at"])
        hours = max(0.0, (first["start_at"] - g.now).total_seconds() / 3600)
        soon = 1 - hours / (cfg.availability_horizon_days * 24)
        add("availability_soon", soon, f"Earliest slot {first['date']} {first['start_time']}", f"Available {_relative_when(first, g.today)}")
        if include_depth:
            add("availability_depth", len(slots) / cfg.availability_depth_target, f"{len(slots)} open slot(s) in the period",
                f"{len(slots)} open slot(s) in the selected period")

        t_from = time_to_str(c.preferred_time_from) if c.preferred_time_from else None
        t_to = time_to_str(c.preferred_time_to) if c.preferred_time_to else None
        if t_from or t_to:
            hit = any(_in_window(s["start_time"], t_from, t_to) for s in slots)
            add("preferred_time", 1.0 if hit else 0.0, "Has slots in your preferred time range" if hit else "No slots in your preferred time range",
                "Slot in preferred time range")

        if c.latitude is not None and c.longitude is not None:
            limit = c.max_distance_km or cfg.location_max_distance_km
            dists = [
                haversine_km(c.latitude, c.longitude, loc["latitude"], loc["longitude"])
                for h in slot_hospitals
                if (loc := g.hospitals.get(h, {}).get("location", {})).get("latitude") is not None
            ]
            if dists:
                d = min(dists)
                add("location", 1 - d / limit, f"{d:.1f} km from you", f"About {d:.1f} km away")
            else:
                add("location", 0.0, "Hospital location unknown")
        elif c.city:
            hit = any(g.hospitals.get(h, {}).get("location", {}).get("city_normalized") == normalize(c.city) for h in slot_hospitals)
            add("location", 1.0 if hit else 0.0, f"Hospital in {c.city}" if hit else f"Not in {c.city}", f"In {c.city}")

        max_points = sum(x["weight"] for x in comps)
        earned = sum(x["points"] for x in comps)
        return Scored(round(100 * earned / max_points, 2) if max_points else 0.0, comps, factors)

    # ------------------------------------------------------------------ public operations

    def _criteria_applied(self, c: MatchCriteria, g: Gathered) -> dict[str, Any]:
        applied = c.model_dump(exclude_none=True, mode="json")
        applied["date_from"], applied["date_to"] = g.date_from, g.date_to
        return applied

    async def match_doctors(self, c: MatchCriteria, page: int, page_size: int) -> dict[str, Any]:
        g = await self.gather(c)
        results = []
        for d in g.doctors:
            slots = g.slots_by_doctor[d["_id"]]
            sc = self.score(g, d, slots, c)
            first = slots[0]
            results.append({
                "doctor_id": str(d["_id"]), "doctor_name": d["name"], "specialty": d["specialty"],
                "hospital_ids": [str(h) for h in sorted({s["hospital_id"] for s in slots})],
                "consultation_fee": d.get("consultation_fee", 0.0), "match_score": sc.score, "match_factors": sc.factors,
                "score_breakdown": sc.components, "next_available": slot_option(first),
                "upcoming_slots": [slot_option(s) for s in self._preview(slots, c)],
                "_sort": (-sc.score, first["start_at"], d["name"]),
            })
        results.sort(key=lambda r: r["_sort"])
        for r in results:
            r.pop("_sort")
        total = len(results)
        start = (page - 1) * page_size
        return {
            "items": results[start : start + page_size], "page": page, "page_size": page_size, "total": total,
            "total_pages": -(-total // page_size) if total else 0, "criteria_applied": self._criteria_applied(c, g),
        }

    @staticmethod
    def _preview(slots: list[dict], c: MatchCriteria) -> list[dict]:
        t_from = time_to_str(c.preferred_time_from) if c.preferred_time_from else None
        t_to = time_to_str(c.preferred_time_to) if c.preferred_time_to else None
        if t_from or t_to:
            slots = sorted(slots, key=lambda s: (not _in_window(s["start_time"], t_from, t_to), s["start_at"]))
        return slots[:SLOTS_PER_DOCTOR]
