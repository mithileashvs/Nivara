"""Consultation notes and document metadata. Notes are written by doctors; SmartCare generates nothing."""
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.database.collections import C
from app.models.clinical import MedicalRecord
from app.models.enums import AppointmentStatus, UserRole
from app.schemas.clinical import DocumentCreate, MedicalRecordCreate
from app.services.storage_service import get_storage
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate
from app.utils.time_utils import utcnow


class MedicalRecordService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.storage = get_storage(settings)

    @property
    def coll(self) -> Any:
        return self.db[C.MEDICAL_RECORDS]

    async def create(self, doctor_id: ObjectId, payload: MedicalRecordCreate) -> dict:
        appt = await self.db[C.APPOINTMENTS].find_one({"_id": oid(payload.appointment_id), "doctor_id": doctor_id})
        if appt is None:
            raise NotFoundError("Appointment not found", code="appointment_not_found")
        if appt["status"] not in (AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED):
            raise ConflictError("Notes can only be added to confirmed or completed appointments", code="invalid_appointment_status")
        doc = MedicalRecord(patient_id=appt["patient_id"], doctor_id=doctor_id, appointment_id=appt["_id"], notes=payload.notes).to_mongo()
        try:
            await self.coll.insert_one(doc)
        except DuplicateKeyError:
            raise ConflictError("A medical record already exists for this appointment", code="record_exists") from None
        return doc

    def _scope(self, role: str, profile_id: ObjectId) -> dict[str, Any]:
        # Patients see only their own records; doctors only records they authored. Admins: none.
        return {"patient_id": profile_id} if role == UserRole.PATIENT else {"doctor_id": profile_id}

    async def get(self, role: str, profile_id: ObjectId, record_id: str) -> dict:
        doc = await self.coll.find_one({"_id": oid(record_id), **self._scope(role, profile_id)})
        if doc is None:
            raise NotFoundError("Medical record not found", code="record_not_found")
        return doc

    async def list(self, role: str, profile_id: ObjectId, params: PageParams, *, patient_id: str | None, appointment_id: str | None) -> tuple[list[dict], int]:
        query = self._scope(role, profile_id)
        if patient_id and role == UserRole.DOCTOR:
            query["patient_id"] = oid(patient_id)
        if appointment_id:
            query["appointment_id"] = oid(appointment_id)
        return await paginate(self.coll, query, params, sort=[("created_at", -1)])

    async def update_notes(self, doctor_id: ObjectId, record_id: str, notes: str) -> dict:
        doc = await self.coll.find_one_and_update(
            {"_id": oid(record_id), "doctor_id": doctor_id}, {"$set": {"notes": notes, "updated_at": utcnow()}}, return_document=True
        )
        if doc is None:
            raise NotFoundError("Medical record not found", code="record_not_found")
        return doc

    async def add_document(self, role: str, profile_id: ObjectId, user_id: ObjectId, record_id: str, payload: DocumentCreate) -> dict:
        record = await self.get(role, profile_id, record_id)
        meta = {
            "id": ObjectId(), "filename": payload.filename, "file_url": self.storage.validate_reference(str(payload.file_url)),
            "document_type": payload.document_type.value, "uploaded_by": user_id, "uploader_role": role, "uploaded_at": utcnow(),
        }
        return await self.coll.find_one_and_update(
            {"_id": record["_id"]}, {"$push": {"documents": meta}, "$set": {"updated_at": utcnow()}}, return_document=True
        )

    async def remove_document(self, user_id: ObjectId, role: str, profile_id: ObjectId, record_id: str, document_id: str) -> dict:
        record = await self.get(role, profile_id, record_id)
        # Only the uploader may remove a document.
        doc = await self.coll.find_one_and_update(
            {"_id": record["_id"], "documents": {"$elemMatch": {"id": oid(document_id), "uploaded_by": user_id}}},
            {"$pull": {"documents": {"id": oid(document_id)}}, "$set": {"updated_at": utcnow()}},
            return_document=True,
        )
        if doc is None:
            raise NotFoundError("Document not found or not uploaded by you", code="document_not_found")
        return doc
