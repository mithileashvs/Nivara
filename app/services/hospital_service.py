"""Hospitals, departments, appointment-intake control, and slot-based availability reporting."""
import re
from datetime import date, timedelta
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.database.collections import C
from app.models.enums import DepartmentStatus, IntakeStatus, ProfileStatus, SlotStatus, UserRole
from app.models.facilities import Department, Hospital
from app.schemas.facilities import DepartmentCreate, DepartmentUpdate, HospitalCreate, HospitalUpdate
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate
from app.utils.text import normalize
from app.utils.time_utils import date_to_str, today_local, utcnow


def can_manage_hospital(user: dict, hospital_id: ObjectId) -> bool:
    """Platform admins (managed_hospital_ids is None) manage everything; hospital administrators only
    the hospitals listed in their scope. Non-admins never manage hospitals."""
    if user["role"] != UserRole.ADMIN:
        return False
    scope = user.get("managed_hospital_ids")
    return scope is None or hospital_id in scope


def assert_can_manage_hospital(user: dict, hospital_id: ObjectId) -> None:
    if not can_manage_hospital(user, hospital_id):
        raise ForbiddenError("You are not authorised to manage this hospital", code="hospital_scope_forbidden")


class HospitalService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ hospitals

    async def create_hospital(self, user: dict, payload: HospitalCreate) -> dict:
        if user.get("managed_hospital_ids") is not None:
            raise ForbiddenError("Only platform administrators can create hospitals", code="platform_admin_required")
        doc = Hospital(
            name=payload.name,
            address=payload.address,
            location=payload.location.model_dump(),
            contact=payload.contact.model_dump(mode="json") if payload.contact else {},
        ).to_mongo()
        await self.db[C.HOSPITALS].insert_one(doc)
        return doc

    async def get_hospital(self, hospital_id: str) -> dict:
        doc = await self.db[C.HOSPITALS].find_one({"_id": oid(hospital_id)})
        if doc is None:
            raise NotFoundError("Hospital not found", code="hospital_not_found")
        return doc

    async def get_hospital_detail(self, hospital_id: str) -> dict:
        doc = await self.get_hospital(hospital_id)
        deps = await self.db[C.DEPARTMENTS].find({"hospital_id": doc["_id"]}).sort("name_normalized", 1).to_list(length=500)
        return {**doc, "departments": deps}

    async def list_hospitals(
        self, params: PageParams, *, city: str | None, q: str | None, intake: IntakeStatus | None
    ) -> tuple[list[dict], int]:
        query: dict[str, Any] = {}
        if city:
            query["location.city_normalized"] = normalize(city)
        if q:
            query["name_normalized"] = {"$regex": re.escape(normalize(q))}
        if intake:
            query["appointment_intake_status"] = intake.value
        return await paginate(self.db[C.HOSPITALS], query, params, sort=[("name_normalized", 1)])

    async def update_hospital(self, user: dict, hospital_id: str, payload: HospitalUpdate) -> dict:
        hospital = await self.get_hospital(hospital_id)
        assert_can_manage_hospital(user, hospital["_id"])
        fields = payload.model_dump(exclude_unset=True, mode="json")
        changes: dict[str, Any] = {}
        if "name" in fields:
            changes["name"], changes["name_normalized"] = fields["name"], normalize(fields["name"])
        if "address" in fields:
            changes["address"] = fields["address"]
        if fields.get("location"):
            changes["location"] = {**fields["location"], "city_normalized": normalize(fields["location"]["city"])}
        if fields.get("contact") is not None:
            changes["contact"] = fields["contact"]
        if not changes:
            return hospital
        changes["updated_at"] = utcnow()
        return await self.db[C.HOSPITALS].find_one_and_update({"_id": hospital["_id"]}, {"$set": changes}, return_document=True)

    # ------------------------------------------------------------------ departments

    async def get_department(self, department_id: str) -> dict:
        doc = await self.db[C.DEPARTMENTS].find_one({"_id": oid(department_id)})
        if doc is None:
            raise NotFoundError("Department not found", code="department_not_found")
        return doc

    async def create_department(self, user: dict, payload: DepartmentCreate) -> dict:
        hospital = await self.get_hospital(payload.hospital_id)
        assert_can_manage_hospital(user, hospital["_id"])
        doc = Department(hospital_id=hospital["_id"], name=payload.name, description=payload.description).to_mongo()
        try:
            await self.db[C.DEPARTMENTS].insert_one(doc)
        except DuplicateKeyError:
            raise ConflictError("A department with this name already exists in the hospital", code="department_exists") from None
        await self.db[C.HOSPITALS].update_one({"_id": hospital["_id"]}, {"$addToSet": {"department_ids": doc["_id"]}})
        return doc

    async def list_departments(
        self, params: PageParams, *, hospital_id: str | None, status: DepartmentStatus | None
    ) -> tuple[list[dict], int]:
        query: dict[str, Any] = {}
        if hospital_id:
            query["hospital_id"] = oid(hospital_id)
        if status:
            query["status"] = status.value
        return await paginate(self.db[C.DEPARTMENTS], query, params, sort=[("hospital_id", 1), ("name_normalized", 1)])

    async def update_department(self, user: dict, department_id: str, payload: DepartmentUpdate) -> dict:
        dept = await self.get_department(department_id)
        assert_can_manage_hospital(user, dept["hospital_id"])
        fields = payload.model_dump(exclude_unset=True, mode="json")
        if "name" in fields:
            fields["name_normalized"] = normalize(fields["name"])
        if not fields:
            return dept
        fields["updated_at"] = utcnow()
        try:
            return await self.db[C.DEPARTMENTS].find_one_and_update({"_id": dept["_id"]}, {"$set": fields}, return_document=True)
        except DuplicateKeyError:
            raise ConflictError("A department with this name already exists in the hospital", code="department_exists") from None

    # ------------------------------------------------------------------ intake control

    async def set_intake(
        self, user: dict, *, target_type: str, target_id: str, status: IntakeStatus, reason: str | None
    ) -> dict[str, Any]:
        """Open/close NEW appointment intake. Existing REQUESTED/CONFIRMED appointments are never touched."""
        if target_type == "HOSPITAL":
            target = await self.get_hospital(target_id)
            hospital_id, coll, appt_filter = target["_id"], C.HOSPITALS, {"hospital_id": target["_id"]}
        else:
            target = await self.get_department(target_id)
            hospital_id, coll, appt_filter = target["hospital_id"], C.DEPARTMENTS, {"department_id": target["_id"]}
        assert_can_manage_hospital(user, hospital_id)

        previous = IntakeStatus(target["appointment_intake_status"])
        await self.db[coll].update_one(
            {"_id": target["_id"]}, {"$set": {"appointment_intake_status": status.value, "updated_at": utcnow()}}
        )
        await self.db[C.INTAKE_EVENTS].insert_one(
            {
                "_id": ObjectId(), "target_type": target_type, "target_id": target["_id"], "hospital_id": hospital_id,
                "previous_status": previous.value, "new_status": status.value, "changed_by": user["_id"],
                "reason": reason, "created_at": utcnow(),
            }
        )
        unaffected = await self.db[C.APPOINTMENTS].count_documents({**appt_filter, "is_active": True})
        label = "hospital" if target_type == "HOSPITAL" else "department"
        verb = "closed" if status == IntakeStatus.CLOSED else "opened"
        return {
            "target_type": target_type,
            "target_id": target["_id"],
            "previous_status": previous,
            "appointment_intake_status": status,
            "active_appointments_unaffected": unaffected,
            "message": f"Appointment intake {verb} for this {label}. Existing requested/confirmed appointments are unchanged.",
        }

    # ------------------------------------------------------------------ availability report

    async def availability_report(self, hospital_id: str, date_from: date | None, date_to: date | None) -> dict[str, Any]:
        """Availability derived ONLY from explicit intake flags and actual open slots — never from
        appointment counts or guessed 'load'."""
        hospital = await self.get_hospital(hospital_id)
        today = today_local(self.settings.app_timezone)
        start = max(date_from or today, today)
        end = date_to or start + timedelta(days=14)
        if end < start or (end - start).days > 31:
            raise BadRequestError("Invalid date range (max 31 days)", code="invalid_date_range")

        departments = await self.db[C.DEPARTMENTS].find({"hospital_id": hospital["_id"]}).sort("name_normalized", 1).to_list(length=500)
        hospital_open = hospital["appointment_intake_status"] == IntakeStatus.OPEN

        eligible = [
            d["_id"] async for d in self.db[C.DOCTORS].find(
                {"hospital_ids": hospital["_id"], "profile_status": ProfileStatus.ACTIVE, "availability_status": IntakeStatus.OPEN}, {"_id": 1}
            )
        ]
        now = utcnow()
        counts: dict[ObjectId, int] = {}
        if hospital_open and eligible:
            rows = await self.db[C.APPOINTMENT_SLOTS].aggregate(
                [
                    {"$match": {
                        "hospital_id": hospital["_id"], "doctor_id": {"$in": eligible},
                        "date": {"$gte": date_to_str(start), "$lte": date_to_str(end)},
                        "start_at": {"$gte": now + timedelta(minutes=self.settings.min_booking_lead_minutes)},
                        "$or": [{"status": SlotStatus.AVAILABLE}, {"status": SlotStatus.HELD, "held_until": {"$lt": now}}],
                    }},
                    {"$group": {"_id": "$department_id", "n": {"$sum": 1}}},
                ]
            ).to_list(length=None)
            counts = {r["_id"]: r["n"] for r in rows}

        dept_out, total = [], 0
        for d in departments:
            accepting = hospital_open and d["status"] == DepartmentStatus.ACTIVE and d["appointment_intake_status"] == IntakeStatus.OPEN
            n = counts.get(d["_id"], 0) if accepting else 0
            if not hospital_open:
                msg = "Appointment intake is closed for this hospital."
            elif d["status"] != DepartmentStatus.ACTIVE:
                msg = "This department is not active."
            elif d["appointment_intake_status"] != IntakeStatus.OPEN:
                msg = "Appointment intake is closed for this department."
            elif n == 0:
                msg = "No available appointment slots in the selected period."
            else:
                msg = f"{n} appointment slot(s) available."
            total += n
            dept_out.append({
                "department_id": d["_id"], "name": d["name"], "department_status": d["status"],
                "appointment_intake_status": d["appointment_intake_status"], "bookable_slots": n,
                "accepting_new_requests": accepting and n > 0, "message": msg,
            })
        if not hospital_open:
            message = "Appointment intake is closed for this hospital."
        elif total == 0:
            message = "No available appointment slots in the selected period."
        else:
            message = f"{total} appointment slot(s) available."
        return {
            "hospital_id": hospital["_id"], "name": hospital["name"],
            "appointment_intake_status": hospital["appointment_intake_status"],
            "accepting_new_requests": hospital_open and total > 0,
            "total_bookable_slots": total, "departments": dept_out, "message": message,
        }
