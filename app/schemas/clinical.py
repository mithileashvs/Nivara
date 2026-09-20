from pydantic import AnyHttpUrl, Field

from app.models.enums import DocumentType
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
