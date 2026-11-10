from pydantic import AnyHttpUrl, Field

from app.models.enums import (
    DocumentConsentStatus,
    DocumentType,
    MedicalAuditAction,
    MedicalDocumentCategory,
)
from app.schemas.common import RequestModel, ResponseModel, UTCDateTime
from app.utils.object_id import ObjectIdStr


class DocumentCreate(RequestModel):
    """Metadata for a file that already lives in external object storage."""

    filename: str = Field(min_length=1, max_length=200)
    file_url: AnyHttpUrl
    document_type: DocumentType = DocumentType.OTHER


class DocumentOut(ResponseModel):
    id: str
    filename: str
    file_url: str
    document_type: DocumentType
    uploaded_by: str
    uploaded_at: UTCDateTime


class DocumentShareCreate(RequestModel):
    doctor_id: str
    appointment_id: str | None = None
    notes: str | None = None


class DocumentShareOut(ResponseModel):
    id: str
    document_id: str
    patient_id: str
    doctor_id: str
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    appointment_id: str | None = None
    consent_status: DocumentConsentStatus
    granted_at: UTCDateTime
    revoked_at: UTCDateTime | None = None
    notes: str | None = None
    created_at: UTCDateTime


class MedicalDocumentOut(ResponseModel):
    id: str
    patient_id: str
    title: str
    category: MedicalDocumentCategory
    description: str | None = None
    filename: str
    file_type: str
    file_size: int
    appointment_id: str | None = None
    patient_name: str | None = None
    shared_at: UTCDateTime | None = None
    share_notes: str | None = None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    shares: list[DocumentShareOut] = Field(default_factory=list)
    download_url: str | None = None


class MedicalTimelineItem(ResponseModel):
    id: str
    item_type: str  # DOCUMENT, APPOINTMENT, CONSULTATION_NOTE
    timestamp: UTCDateTime
    date: str
    title: str
    category: str | None = None
    description: str | None = None
    doctor_name: str | None = None
    status: str | None = None
    reference_id: str
    metadata: dict = Field(default_factory=dict)


class MedicalAuditOut(ResponseModel):
    id: str
    actor_id: str | None = None
    actor_role: str
    patient_id: str | None = None
    document_id: str | None = None
    action: str
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: UTCDateTime


class MedicalStatsOut(ResponseModel):
    total_documents: int
    total_size_bytes: int
    total_shares: int
    active_shares: int
    category_counts: dict[str, int] = Field(default_factory=dict)


class MedicalRecordCreate(RequestModel):
    appointment_id: ObjectIdStr
    notes: str = Field(min_length=1, max_length=10_000, description="Consultation notes written by the doctor")


class MedicalRecordUpdate(RequestModel):
    notes: str = Field(min_length=1, max_length=10_000)


class MedicalRecordOut(ResponseModel):
    id: str
    patient_id: str
    doctor_id: str
    appointment_id: str
    notes: str
    documents: list[DocumentOut]
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ReviewCreate(RequestModel):
    appointment_id: ObjectIdStr
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewPublicOut(ResponseModel):
    """Public view — patient identity is not exposed."""

    id: str
    doctor_id: str
    rating: int
    comment: str | None = None
    created_at: UTCDateTime


class ReviewOwnOut(ReviewPublicOut):
    patient_id: str
    appointment_id: str
