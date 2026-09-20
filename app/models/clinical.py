from bson import ObjectId
from pydantic import Field

from app.models.base import MongoModel


class MedicalRecord(MongoModel):
    patient_id: ObjectId
    doctor_id: ObjectId
    appointment_id: ObjectId
    notes: str  # written by the doctor; SmartCare never generates clinical content
    documents: list[dict] = Field(default_factory=list)  # metadata only


class Review(MongoModel):
    patient_id: ObjectId
    doctor_id: ObjectId
    appointment_id: ObjectId
    rating: int
    comment: str | None = None
