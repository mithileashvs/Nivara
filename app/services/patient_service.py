from typing import Any

from bson import ObjectId

from app.core.errors import NotFoundError
from app.database.collections import C
from app.models.enums import AppointmentStatus
from app.schemas.users import PatientUpdate
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate
from app.utils.time_utils import utcnow


def merge_patient(patient: dict, user: dict) -> dict:
    return {**patient, "name": user["name"], "email": user["email"], "phone": user.get("phone")}


class PatientService:
    def __init__(self, db: Any) -> None:
        self.db = db

    async def update_me(self, user: dict, patient: dict, payload: PatientUpdate) -> dict:
        now = utcnow()
        user_set: dict[str, Any] = {}
        if payload.name is not None:
            user_set["name"] = payload.name
        if payload.phone is not None:
            user_set["phone"] = payload.phone
        if user_set:
            user_set["updated_at"] = now
            user = await self.db[C.USERS].find_one_and_update({"_id": user["_id"]}, {"$set": user_set}, return_document=True)

        p_set: dict[str, Any] = {}
        if payload.date_of_birth is not None:
            p_set["date_of_birth"] = payload.date_of_birth.isoformat()
        if payload.gender is not None:
            p_set["gender"] = payload.gender.value
        if payload.basic_information is not None:
            for k, v in payload.basic_information.model_dump(exclude_unset=True).items():
                p_set[f"basic_information.{k}"] = v
        if p_set or user_set:
            p_set["updated_at"] = now
            patient = await self.db[C.PATIENTS].find_one_and_update(
                {"_id": patient["_id"]}, {"$set": p_set}, return_document=True
            )
        return merge_patient(patient, user)

    async def get_for_doctor(self, doctor_id: ObjectId, patient_id: str) -> dict:
        """A doctor may only see patients they have (or had) an appointment with."""
        pid = oid(patient_id)
        related = await self.db[C.APPOINTMENTS].find_one(
            {
                "doctor_id": doctor_id,
                "patient_id": pid,
                "status": {"$in": [AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW]},
            },
            {"_id": 1},
        )
        if related is None:
            raise NotFoundError("Patient not found")  # 404, not 403: don't reveal existence
        patient = await self.db[C.PATIENTS].find_one({"_id": pid})
        user = await self.db[C.USERS].find_one({"_id": patient["user_id"]})
        return merge_patient(patient, user)

    async def list_for_admin(self, params: PageParams) -> tuple[list[dict], int]:
        docs, total = await paginate(self.db[C.PATIENTS], {}, params, sort=[("created_at", -1)])
        users = {
            u["_id"]: u
            async for u in self.db[C.USERS].find({"_id": {"$in": [d["user_id"] for d in docs]}}, {"name": 1})
        }
        return [
            {"_id": d["_id"], "user_id": d["user_id"], "name": users.get(d["user_id"], {}).get("name", ""), "created_at": d["created_at"]}
            for d in docs
        ], total
