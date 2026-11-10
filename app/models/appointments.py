from datetime import datetime
from typing import Any

from app.models.base import EntityModel
from app.models.enums import AppointmentStatus, ReschedulingStatus


class Appointment(EntityModel):
    patient_id: str
    patient_user_id: str
    patient_name: str  # snapshot at booking time
    doctor_id: str
    doctor_user_id: str
    doctor_name: str  # snapshot at booking time
    hospital_id: str
    department_id: str
    slot_id: str
    appointment_date: str
    start_time: str
    end_time: str
    start_at: datetime
    end_at: datetime
    consultation_type: str
    reason: str | None = None
    status: AppointmentStatus = AppointmentStatus.REQUESTED
    is_active: bool = True
    status_reason: str | None = None
    reminder_sent: bool = False


class ReschedulingRequest(EntityModel):
    appointment_id: str
    patient_id: str
    patient_user_id: str
    patient_name: str | None = None
    doctor_id: str
    doctor_user_id: str
    doctor_name: str | None = None
    hospital_id: str
    department_id: str
    old_slot_id: str
    requested_slot_id: str
    old_appointment_date: str | None = None
    old_start_time: str | None = None
    old_end_time: str | None = None
    requested_appointment_date: str | None = None
    requested_start_time: str | None = None
    requested_end_time: str | None = None
    reason: str
    status: ReschedulingStatus = ReschedulingStatus.REQUESTED
    doctor_response: str | None = None
    resolved_at: datetime | None = None


class AppointmentHistory(EntityModel):
    appointment_id: str
    previous_status: str | None
    new_status: str
    changed_by: str | None  # user id; None => system
    changed_by_role: str  # PATIENT | DOCTOR | SYSTEM
    reason: str | None = None
    previous_date: str | None = None
    previous_time: str | None = None
    new_date: str | None = None
    new_time: str | None = None
    metadata: dict[str, Any] | None = None
