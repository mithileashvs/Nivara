import re
from datetime import date, timedelta
from typing import Any

from app.core.config import Settings
from app.core.errors import BadRequestError, NotFoundError
from app.database.collections import C
from app.models.enums import (
    AuditAction,
    AuditActorRole,
    AuditEntityType,
    AuditSeverity,
    IntakeStatus,
    NotificationType,
    ProfileStatus,
    SlotStatus,
)
from app.schemas.users import DoctorAffiliationUpdate, DoctorSearchParams, DoctorUpdate
from app.services.audit_service import AuditService
from app.services.intake_service import IntakeService
from app.services.notification_service import NotificationService
from app.utils.geo import haversine_km
from app.utils.object_id import oid, oids
from app.utils.pagination import PageParams, paginate
from app.utils.text import normalize
from app.utils.time_utils import date_to_str, today_local, utcnow


def doctor_view(doc: dict) -> dict:
    count = doc.get("rating_count", 0)
    return {**doc, "rating_average": round(doc.get("rating_sum", 0) / count, 2) if count else None}


class DoctorService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.intake = IntakeService(db)
        self.audit = AuditService(db, settings)

    @property
    def coll(self) -> Any:
        return self.db[C.DOCTORS]

    async def get_public(self, doctor_id: str) -> dict:
        doc = await self.coll.find_one({"_id": oid(doctor_id), "profile_status": ProfileStatus.ACTIVE})
        if doc is None:
            raise NotFoundError("Doctor not found", code="doctor_not_found")
        return doctor_view(doc)

    async def get_any(self, doctor_id: str) -> dict:
        doc = await self.coll.find_one({"_id": oid(doctor_id)})
        if doc is None:
            raise NotFoundError("Doctor not found", code="doctor_not_found")
        return doc

    # ------------------------------------------------------------------ search

    async def hospital_filter(
        self, *, hospital_id: str | None, city: str | None, lat: float | None, lon: float | None, max_km: float | None
    ) -> set[str] | None:
        """Hospital ids satisfying hard hospital-level filters, or None if unconstrained."""
        allowed: set[str] | None = None

        def narrow(ids: set[str]) -> None:
            nonlocal allowed
            allowed = ids if allowed is None else allowed & ids

        if hospital_id:
            narrow({oid(hospital_id)})
        if city:
            narrow({h["_id"] async for h in self.db[C.HOSPITALS].find({"location.city_normalized": normalize(city)}, {"_id": 1})})
        if lat is not None and lon is not None and max_km is not None:
            near = set()
            async for h in self.db[C.HOSPITALS].find({"location.latitude": {"$ne": None}}, {"location": 1}):
                loc = h["location"]
                if loc.get("latitude") is not None and haversine_km(lat, lon, loc["latitude"], loc["longitude"]) <= max_km:
                    near.add(h["_id"])
            narrow(near)
        return allowed

    async def build_query(
        self,
        *,
        doctor_id: str | None = None,
        q: str | None = None,
        specialty: str | None = None,
        department_id: str | None = None,
        hospital_id: str | None = None,
        consultation_type: str | None = None,
        city: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        max_km: float | None = None,
        only_open: bool = False,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"profile_status": ProfileStatus.ACTIVE}
        if only_open:
            query["availability_status"] = IntakeStatus.OPEN
        if doctor_id:
            query["_id"] = oid(doctor_id)
        if q:
            query["name"] = {"$regex": re.escape(q), "$options": "i"}
        if specialty:
            query["specialty_normalized"] = {"$regex": "^" + re.escape(normalize(specialty))}
        if department_id:
            query["department_ids"] = oid(department_id)
        if consultation_type:
            query["consultation_types"] = str(consultation_type)
        hospitals = await self.hospital_filter(hospital_id=hospital_id, city=city, lat=lat, lon=lon, max_km=max_km)
        if hospitals is not None:
            query["hospital_ids"] = {"$in": list(hospitals)}
        return query

    async def doctor_ids_with_bookable_slots(self, date_from: str, date_to: str) -> list[str]:
        now = utcnow()
        open_h, open_d = await self.intake.open_scope()
        if not open_h or not open_d:
            return []
        match = {
            "hospital_id": {"$in": open_h},
            "department_id": {"$in": open_d},
            "date": {"$gte": date_from, "$lte": date_to},
            "start_at": {"$gte": now + timedelta(minutes=self.settings.min_booking_lead_minutes)},
            "$or": [{"status": SlotStatus.AVAILABLE}, {"status": SlotStatus.HELD, "held_until": {"$lt": now}}],
        }
        rows = await self.db[C.APPOINTMENT_SLOTS].aggregate(
            [{"$match": match}, {"$group": {"_id": "$doctor_id"}}]
        ).to_list(length=None)
        return [r["_id"] for r in rows]

    async def search(self, f: DoctorSearchParams, params: PageParams) -> tuple[list[dict], int]:
        if (f.latitude is None) != (f.longitude is None):
            raise BadRequestError("latitude and longitude must be provided together", code="invalid_location")
        if f.max_distance_km is not None and f.latitude is None:
            raise BadRequestError("max_distance_km requires latitude and longitude", code="invalid_location")
        query = await self.build_query(
            q=f.q, specialty=f.specialty, department_id=f.department_id, hospital_id=f.hospital_id,
            consultation_type=f.consultation_type, city=f.city, lat=f.latitude, lon=f.longitude,
            max_km=f.max_distance_km, only_open=f.available,
        )
        if f.available:
            today = today_local(self.settings.app_timezone)
            start = max(f.date_from or today, today)
            end = f.date_to or start + timedelta(days=14)
            if end < start or (end - start).days > 60:
                raise BadRequestError("Invalid date range (max 60 days)", code="invalid_date_range")
            ids = await self.doctor_ids_with_bookable_slots(date_to_str(start), date_to_str(end))
            query = {"$and": [query, {"_id": {"$in": ids}}]}
        docs, total = await paginate(self.coll, query, params, sort=[("name", 1), ("_id", 1)])
        return [doctor_view(d) for d in docs], total

    # ------------------------------------------------------------------ updates

    async def update_me(self, doctor: dict, payload: DoctorUpdate) -> dict:
        fields = payload.model_dump(exclude_unset=True, mode="json")
        if not fields:
            return doctor_view(doctor)
        fields["updated_at"] = utcnow()
        doc = await self.coll.find_one_and_update({"_id": doctor["_id"]}, {"$set": fields}, return_document=True)
        return doctor_view(doc)

    async def set_intake(
        self,
        doctor_id: str,
        status: IntakeStatus,
        *,
        actor: dict | None = None,
        reason: str | None = None,
    ) -> tuple[dict, IntakeStatus]:
        doctor = await self.get_any(doctor_id)
        previous = IntakeStatus(doctor["availability_status"])
        doc = await self.coll.find_one_and_update(
            {"_id": doctor["_id"]}, {"$set": {"availability_status": status.value, "updated_at": utcnow()}}, return_document=True
        )
        hosp_ids = doctor.get("hospital_ids") or []
        await self.audit.log_event(
            action=AuditAction.DOCTOR_INTAKE_UPDATED,
            entity_type=AuditEntityType.DOCTOR,
            entity_id=doctor["_id"],
            actor_id=actor["_id"] if actor else None,
            actor_role=str(actor["role"]) if actor else AuditActorRole.ADMIN,
            hospital_id=str(hosp_ids[0]) if len(hosp_ids) == 1 else None,
            description=f"Doctor {doctor['name']} intake changed from {previous.value} to {status.value}",
            metadata={"previous_status": previous.value, "new_status": status.value, "reason": reason, "hospital_ids": hosp_ids},
        )
        return doctor_view(doc), previous

    async def set_affiliations(
        self,
        doctor_id: str,
        payload: DoctorAffiliationUpdate,
        *,
        actor: dict | None = None,
    ) -> dict:
        doctor = await self.get_any(doctor_id)
        prev_hospitals = list(doctor.get("hospital_ids") or [])
        prev_depts = list(doctor.get("department_ids") or [])
        hospital_ids, dept_ids = oids(payload.hospital_ids), oids(payload.department_ids)
        hospitals = await self.db[C.HOSPITALS].count_documents({"_id": {"$in": hospital_ids}})
        if hospitals != len(set(hospital_ids)):
            raise BadRequestError("One or more hospitals do not exist", code="invalid_hospital")
        depts = await self.db[C.DEPARTMENTS].find({"_id": {"$in": dept_ids}}, {"hospital_id": 1}).to_list(length=None)
        if len(depts) != len(set(dept_ids)) or any(d["hospital_id"] not in hospital_ids for d in depts):
            raise BadRequestError(
                "Every department must exist and belong to one of the listed hospitals", code="invalid_department"
            )
        clean_hospitals = list(dict.fromkeys(hospital_ids))
        clean_depts = list(dict.fromkeys(dept_ids))
        doc = await self.coll.find_one_and_update(
            {"_id": doctor["_id"]},
            {"$set": {"hospital_ids": clean_hospitals, "department_ids": clean_depts, "updated_at": utcnow()}},
            return_document=True,
        )
        await self.audit.log_event(
            action=AuditAction.DOCTOR_AFFILIATIONS_UPDATED,
            entity_type=AuditEntityType.DOCTOR,
            entity_id=doctor["_id"],
            actor_id=actor["_id"] if actor else None,
            actor_role=str(actor["role"]) if actor else AuditActorRole.ADMIN,
            hospital_id=str(clean_hospitals[0]) if len(clean_hospitals) == 1 else None,
            description=f"Updated hospital/department affiliations for Dr. {doctor['name']}",
            metadata={
                "doctor_name": doctor["name"],
                "previous_hospital_ids": prev_hospitals,
                "new_hospital_ids": clean_hospitals,
                "previous_department_ids": prev_depts,
                "new_department_ids": clean_depts,
            },
        )
        return doctor_view(doc)

    async def set_profile_status(
        self,
        doctor_id: str,
        status: ProfileStatus,
        *,
        reason: str | None = None,
        actor: dict | None = None,
    ) -> dict:
        doctor = await self.get_any(doctor_id)
        prev_status = str(doctor.get("profile_status") or ProfileStatus.PENDING.value)
        clean_reason = reason.strip() if reason and reason.strip() else None
        doc = await self.coll.find_one_and_update(
            {"_id": doctor["_id"]}, {"$set": {"profile_status": status.value, "updated_at": utcnow()}}, return_document=True
        )
        hosp_ids = doctor.get("hospital_ids") or []
        if status == ProfileStatus.ACTIVE:
            action = AuditAction.DOCTOR_VERIFIED
            severity = AuditSeverity.INFO
            desc = f"Doctor profile verified/activated for {doctor['name']}"
            await NotificationService(self.db).notify(
                user_id=doctor["user_id"],
                type=NotificationType.DOCTOR_VERIFIED.value,
                title="Profile verified and active",
                message="Your doctor profile has been verified by the administrator. You can now publish your schedule and accept appointment requests.",
                category="SYSTEM",
                action_url="/doctor/availability",
            )
        elif status == ProfileStatus.SUSPENDED:
            action = AuditAction.DOCTOR_SUSPENDED
            severity = AuditSeverity.WARNING
            desc = f"Doctor profile suspended/rejected for {doctor['name']}"
            susp_msg = "Your doctor profile has been suspended by an administrator. Please contact your hospital administrator."
            if clean_reason:
                susp_msg += f" Reason: {clean_reason}"
            await NotificationService(self.db).notify(
                user_id=doctor["user_id"],
                type=NotificationType.DOCTOR_SUSPENDED.value,
                title="Profile suspended",
                message=susp_msg,
                category="SYSTEM",
                action_url="/doctor/profile",
            )
        else:
            action = AuditAction.DOCTOR_SET_PENDING
            severity = AuditSeverity.INFO
            desc = f"Doctor profile moved to PENDING for {doctor['name']}"

        await self.audit.log_event(
            action=action,
            entity_type=AuditEntityType.DOCTOR,
            entity_id=doctor["_id"],
            actor_id=actor["_id"] if actor else None,
            actor_role=str(actor["role"]) if actor else AuditActorRole.ADMIN,
            hospital_id=str(hosp_ids[0]) if len(hosp_ids) == 1 else None,
            severity=severity,
            description=desc,
            metadata={
                "doctor_name": doctor["name"],
                "specialty": doctor.get("specialty"),
                "previous_status": prev_status,
                "new_status": status.value,
                "reason": clean_reason,
                "hospital_ids": hosp_ids,
            },
        )
        return doctor_view(doc)

    # ------------------------------------------------------------------ statistics

    async def get_statistics(self, doctor: dict) -> dict:
        """Basic counts for the authenticated doctor. Every value is a live database count."""
        appts = self.db[C.APPOINTMENTS]
        doctor_id = doctor["_id"]
        today_str = date_to_str(today_local(self.settings.app_timezone))

        todays_appointments = await appts.count_documents({
            "doctor_id": doctor_id, "appointment_date": today_str, "status": {"$in": ["CONFIRMED", "COMPLETED", "NO_SHOW"]},
        })
        pending_requests = await appts.count_documents({"doctor_id": doctor_id, "status": "REQUESTED"})
        pending_reschedule_requests = await self.db[C.RESCHEDULING_REQUESTS].count_documents({
            "doctor_id": doctor_id, "status": "REQUESTED"
        })
        confirmed_appointments = await appts.count_documents({"doctor_id": doctor_id, "status": "CONFIRMED"})
        completed_appointments = await appts.count_documents({"doctor_id": doctor_id, "status": "COMPLETED"})
        patient_rows = await appts.aggregate(
            [{"$match": {"doctor_id": doctor_id}}, {"$group": {"_id": "$patient_id"}}]
        ).to_list(length=None)
        total_patients = len(patient_rows)

        return {
            "todays_appointments": todays_appointments,
            "pending_requests": pending_requests,
            "pending_reschedule_requests": pending_reschedule_requests,
            "confirmed_appointments": confirmed_appointments,
            "completed_appointments": completed_appointments,
            "total_patients": total_patients,
        }
