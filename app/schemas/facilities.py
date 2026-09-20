from pydantic import EmailStr, Field, HttpUrl

from app.models.enums import DepartmentStatus, IntakeStatus
from app.schemas.common import RequestModel, ResponseModel, UTCDateTime
from app.utils.object_id import ObjectIdStr
from app.schemas.auth import PHONE_PATTERN


class HospitalLocation(RequestModel):
    city: str = Field(min_length=1, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class HospitalContact(RequestModel):
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    email: EmailStr | None = None
    website: HttpUrl | None = None


class HospitalCreate(RequestModel):
    name: str = Field(min_length=2, max_length=120)
    address: str = Field(min_length=3, max_length=300)
    location: HospitalLocation
    contact: HospitalContact | None = None


class HospitalUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    address: str | None = Field(default=None, min_length=3, max_length=300)
    location: HospitalLocation | None = None
    contact: HospitalContact | None = None


class DepartmentOut(ResponseModel):
    id: str
    hospital_id: str
    name: str
    description: str | None = None
    status: DepartmentStatus
    appointment_intake_status: IntakeStatus
    created_at: UTCDateTime
    updated_at: UTCDateTime


class HospitalOut(ResponseModel):
    id: str
    name: str
    address: str
    location: dict
    contact: dict
    appointment_intake_status: IntakeStatus
    department_ids: list[str]
    created_at: UTCDateTime
    updated_at: UTCDateTime


class HospitalDetailOut(HospitalOut):
    departments: list[DepartmentOut]


class DepartmentCreate(RequestModel):
    hospital_id: ObjectIdStr
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)


class DepartmentUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    status: DepartmentStatus | None = None


class IntakeUpdateRequest(RequestModel):
    status: IntakeStatus
    reason: str | None = Field(default=None, max_length=300)


class IntakeUpdateResponse(ResponseModel):
    target_type: str
    target_id: str
    previous_status: IntakeStatus
    appointment_intake_status: IntakeStatus
    active_appointments_unaffected: int = Field(
        description="Existing REQUESTED/CONFIRMED appointments — never cancelled by closing intake"
    )
    message: str


class DepartmentAvailabilityOut(ResponseModel):
    department_id: str
    name: str
    department_status: DepartmentStatus
    appointment_intake_status: IntakeStatus
    bookable_slots: int
    accepting_new_requests: bool
    message: str


class HospitalAvailabilityOut(ResponseModel):
    hospital_id: str
    name: str
    appointment_intake_status: IntakeStatus
    accepting_new_requests: bool
    total_bookable_slots: int
    departments: list[DepartmentAvailabilityOut]
    message: str
