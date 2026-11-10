from datetime import datetime
from pydantic import Field

from app.models.base import EntityModel


class MedicalRecord(EntityModel):
    patient_id: str
    doctor_id: str
    appointment_id: str
    notes: str  # written by the doctor
    documents: list[dict] = Field(default_factory=list)  # metadata only


class MedicalDocument(EntityModel):
    patient_id: str
    patient_user_id: str
    title: str
    category: str
    description: str | None = None
    filename: str
    file_type: str
    file_size: int
    storage_path: str
    storage_provider: str = "LOCAL"
    appointment_id: str | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None


class DocumentShare(EntityModel):
    document_id: str
    patient_id: str
    doctor_id: str
    appointment_id: str | None = None
    consent_status: str = "GRANTED"
    granted_at: datetime = Field(default_factory=datetime.utcnow)
    revoked_at: datetime | None = None
    notes: str | None = None


class MedicalRecordAudit(EntityModel):
    actor_id: str | None = None
    actor_role: str
    patient_id: str | None = None
    document_id: str | None = None
    action: str
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)


class Review(EntityModel):
    patient_id: str
    doctor_id: str
    appointment_id: str
    rating: int
    comment: str | None = None
