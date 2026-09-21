from typing import Any

from app.database.session import DuplicateKeyError

from app.core.errors import ConflictError, NotFoundError
from app.database.collections import C
from app.models.clinical import Review
from app.models.enums import AppointmentStatus
from app.schemas.clinical import ReviewCreate
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate


class ReviewService:
    def __init__(self, db: Any) -> None:
        self.db = db

    @property
    def coll(self) -> Any:
        return self.db[C.REVIEWS]

    async def create(self, patient_id: Any, payload: ReviewCreate) -> dict:
        appt = await self.db[C.APPOINTMENTS].find_one({"_id": oid(payload.appointment_id), "patient_id": str(patient_id)})
        if appt is None:
            raise NotFoundError("Appointment not found", code="appointment_not_found")
        if appt["status"] != AppointmentStatus.COMPLETED:
            raise ConflictError("Only completed appointments can be reviewed", code="appointment_not_completed")
        doc = Review(patient_id=str(patient_id), doctor_id=appt["doctor_id"], appointment_id=appt["_id"], rating=payload.rating, comment=payload.comment).to_mongo()
        try:
            await self.coll.insert_one(doc)  # unique index on appointment_id prevents duplicates atomically
        except DuplicateKeyError:
            raise ConflictError("This appointment has already been reviewed", code="review_exists") from None
        await self.db[C.DOCTORS].update_one({"_id": appt["doctor_id"]}, {"$inc": {"rating_sum": payload.rating, "rating_count": 1}})
        return doc

    async def list_for_doctor(self, doctor_id: str, params: PageParams) -> tuple[list[dict], int]:
        return await paginate(self.coll, {"doctor_id": oid(doctor_id)}, params, sort=[("created_at", -1)])

    async def list_mine(self, patient_id: Any, params: PageParams) -> tuple[list[dict], int]:
        return await paginate(self.coll, {"patient_id": str(patient_id)}, params, sort=[("created_at", -1)])

    async def delete(self, review_id: str) -> None:
        doc = await self.coll.find_one({"_id": oid(review_id)})
        if doc is None:
            raise NotFoundError("Review not found", code="review_not_found")
        await self.coll.delete_one({"_id": doc["_id"]})
        await self.db[C.DOCTORS].update_one({"_id": doc["doctor_id"]}, {"$inc": {"rating_sum": -doc["rating"], "rating_count": -1}})
