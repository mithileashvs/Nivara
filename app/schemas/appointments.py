from datetime import date

from pydantic import ConfigDict, Field

from app.models.enums import AppointmentStatus, ConsultationType
from app.schemas.common import RequestModel, ResponseModel, UTCDateTime
from app.utils.object_id import ObjectIdStr


class AppointmentCreate(RequestModel):
    slot_id: ObjectIdStr
    consultation_type: ConsultationType = ConsultationType.FIRST_VISIT
    reason: str | None = Field(
        default=None, max_length=500, description="Why the patient wants the visit, in their own words (optional)"
    )


class AppointmentDecision(RequestModel):
    reason: str | None = Field(default=None, max_length=300)


class AppointmentReject(RequestModel):
    reason: str | None = Field(default=None, max_length=300)


class AppointmentReschedule(RequestModel):
    new_slot_id: ObjectIdStr
    reason: str | None = Field(default=None, max_length=300)


class AppointmentOut(ResponseModel):
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    hospital_id: str
    department_id: str
    slot_id: str
    appointment_date: str
    start_time: str
    end_time: str
    start_at: UTCDateTime
    consultation_type: str
    reason: str | None = None
    status: AppointmentStatus
    status_reason: str | None = None
    created_at: UTCDateTime
    updated_at: UTCDateTime


class AppointmentListParams(RequestModel):
    status: AppointmentStatus | None = None
    date_from: date | None = None
    date_to: date | None = None


class AdminAppointmentSearchParams(RequestModel):
    """Query params for the read-only admin appointment listing. Admins monitor only — see
    `app.routes.admin` for why there is no accept/reject here."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")  # used as a query model; pagination params live beside it

    status: AppointmentStatus | None = None
    doctor_id: ObjectIdStr | None = None
    patient_id: ObjectIdStr | None = None
    hospital_id: ObjectIdStr | None = None
    department_id: ObjectIdStr | None = None
    appointment_date: date | None = Field(default=None, description="Exact date (YYYY-MM-DD)")
    date_from: date | None = None
    date_to: date | None = None


class AdminAppointmentOut(ResponseModel):
    """Platform-monitoring view of an appointment. Deliberately excludes the patient's free-text
    `reason` and any other clinical detail — admins monitor the workflow, not medical content."""

    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    hospital_id: str
    hospital_name: str | None = None
    department_id: str
    department_name: str | None = None
    appointment_date: str
    start_time: str
    end_time: str
    consultation_type: str
    status: AppointmentStatus
    created_at: UTCDateTime


class AppointmentHistoryOut(ResponseModel):
    id: str
    appointment_id: str
    previous_status: str | None
    new_status: str
    changed_by: str | None
    changed_by_role: str
    reason: str | None = None
    created_at: UTCDateTime
