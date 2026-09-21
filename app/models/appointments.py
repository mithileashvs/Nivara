from datetime import datetime

from app.models.base import EntityModel
from app.models.enums import AppointmentStatus


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


class AppointmentHistory(EntityModel):
    appointment_id: str
    previous_status: str | None
    new_status: str
    changed_by: str | None  # user id; None => system
    changed_by_role: str  # PATIENT | DOCTOR | SYSTEM
    reason: str | None = None
