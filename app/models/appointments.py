from datetime import datetime

from bson import ObjectId

from app.models.base import MongoModel
from app.models.enums import AppointmentStatus


class Appointment(MongoModel):
    patient_id: ObjectId
    patient_user_id: ObjectId
    patient_name: str  # snapshot at booking time
    doctor_id: ObjectId
    doctor_user_id: ObjectId
    doctor_name: str  # snapshot at booking time
    hospital_id: ObjectId
    department_id: ObjectId
    slot_id: ObjectId
    appointment_date: str
    start_time: str
    end_time: str
    start_at: datetime
    end_at: datetime
    consultation_type: str
    reason: str | None = None
    status: AppointmentStatus = AppointmentStatus.REQUESTED
    # True while the appointment occupies a slot (REQUESTED / CONFIRMED). Drives the
    # partial-unique indexes that guarantee one active appointment per slot.
    is_active: bool = True
    status_reason: str | None = None
    reminder_sent: bool = False


class AppointmentHistory(MongoModel):
    appointment_id: ObjectId
    previous_status: str | None
    new_status: str
    changed_by: ObjectId | None  # user id; None => system
    changed_by_role: str  # PATIENT | DOCTOR | SYSTEM
    reason: str | None = None
