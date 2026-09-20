from datetime import date
from typing import Annotated

from pydantic import ConfigDict, EmailStr, Field, field_validator

from app.models.enums import ConsultationType, Gender, IntakeStatus, ProfileStatus
from app.schemas.auth import PHONE_PATTERN
from app.schemas.common import RequestModel, ResponseModel, UTCDateTime
from app.utils.object_id import ObjectIdStr


class BasicInformation(RequestModel):
    address_line: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=80)
    emergency_contact_name: str | None = Field(default=None, max_length=100)
    emergency_contact_phone: str | None = Field(default=None, pattern=PHONE_PATTERN)


class PatientUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    date_of_birth: date | None = None
    gender: Gender | None = None
    basic_information: BasicInformation | None = None

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date | None) -> date | None:
        if v is not None and (v > date.today() or v.year < 1900):
            raise ValueError("date_of_birth must be a valid past date")
        return v


class PatientOut(ResponseModel):
    """Full profile — returned only to the patient themself."""

    id: str
    user_id: str
    name: str
    email: EmailStr
    phone: str | None = None
    date_of_birth: str | None = None
    gender: Gender
    basic_information: dict
    created_at: UTCDateTime
    updated_at: UTCDateTime


class PatientSummaryForDoctorOut(ResponseModel):
    """Minimum a doctor needs about a patient they have an appointment with."""

    id: str
    name: str
    date_of_birth: str | None = None
    gender: Gender
    phone: str | None = None


class PatientSummaryForAdminOut(ResponseModel):
    """Platform admins see identity only — no health-related or contact details."""

    id: str
    user_id: str
    name: str
    created_at: UTCDateTime


# ---------------- doctors ----------------

class DoctorUpdate(RequestModel):
    """Fields a doctor may change on their own profile.

    Specialty, hospital and department affiliations are platform-verified and are
    changed by an admin.
    """

    experience: int | None = Field(default=None, ge=0, le=70)
    consultation_fee: float | None = Field(default=None, ge=0, le=1_000_000)
    consultation_types: list[ConsultationType] | None = Field(default=None, min_length=1)


class DoctorIntakeUpdate(RequestModel):
    availability_status: IntakeStatus
    reason: str | None = Field(default=None, max_length=300)


class DoctorPublicOut(ResponseModel):
    id: str
    name: str
    specialty: str
    department_ids: list[str]
    hospital_ids: list[str]
    experience: int
    consultation_fee: float
    consultation_types: list[str]
    availability_status: IntakeStatus
    rating_average: float | None = None
    rating_count: int = 0


class DoctorOut(DoctorPublicOut):
    """Own / admin view (adds internal identifiers and profile status)."""

    user_id: str
    profile_status: ProfileStatus
    created_at: UTCDateTime
    updated_at: UTCDateTime


class DoctorSearchParams(RequestModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")  # used as query model: pagination params live beside it
    q: str | None = Field(default=None, max_length=80, description="Doctor name contains")
    specialty: str | None = Field(default=None, max_length=80)
    department_id: ObjectIdStr | None = None
    hospital_id: ObjectIdStr | None = None
    consultation_type: ConsultationType | None = None
    city: str | None = Field(default=None, max_length=80, description="Hospital city")
    available: bool = Field(default=False, description="Only doctors with at least one bookable slot in the date range")
    date_from: date | None = None
    date_to: date | None = None
    latitude: Annotated[float, Field(ge=-90, le=90)] | None = None
    longitude: Annotated[float, Field(ge=-180, le=180)] | None = None
    max_distance_km: float | None = Field(default=None, gt=0, le=500)


class DoctorStatistics(ResponseModel):
    """Basic per-doctor counts for the authenticated doctor, computed live from the database."""

    todays_appointments: int
    pending_requests: int
    confirmed_appointments: int
    completed_appointments: int
    total_patients: int


class DoctorAffiliationUpdate(RequestModel):
    hospital_ids: list[ObjectIdStr] = Field(max_length=20)
    department_ids: list[ObjectIdStr] = Field(max_length=50)


class DoctorProfileStatusUpdate(RequestModel):
    profile_status: ProfileStatus
    reason: str | None = Field(default=None, max_length=300)
