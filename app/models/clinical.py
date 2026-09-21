from pydantic import Field

from app.models.base import EntityModel


class MedicalRecord(EntityModel):
    patient_id: str
    doctor_id: str
    appointment_id: str
    notes: str  # written by the doctor
    documents: list[dict] = Field(default_factory=list)  # metadata only


class Review(EntityModel):
    patient_id: str
    doctor_id: str
    appointment_id: str
    rating: int
    comment: str | None = None
