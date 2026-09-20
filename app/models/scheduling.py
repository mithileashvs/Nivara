from datetime import datetime

from bson import ObjectId

from app.models.base import MongoModel
from app.models.enums import AvailabilityStatus, SlotStatus


class DoctorAvailability(MongoModel):
    doctor_id: ObjectId
    hospital_id: ObjectId
    department_id: ObjectId
    date: str  # "YYYY-MM-DD" (clinic-local)
    start_time: str  # "HH:MM"
    end_time: str
    slot_duration: int  # minutes
    status: AvailabilityStatus = AvailabilityStatus.WORKING
    note: str | None = None


class AppointmentSlot(MongoModel):
    doctor_id: ObjectId
    hospital_id: ObjectId
    department_id: ObjectId
    date: str
    start_time: str
    end_time: str
    start_at: datetime  # naive UTC
    end_at: datetime  # naive UTC
    status: SlotStatus = SlotStatus.AVAILABLE
    appointment_id: ObjectId | None = None
    held_until: datetime | None = None
    availability_id: ObjectId | None = None  # working window that generated the slot
    block_source: str | None = None  # "AVAILABILITY" | "MANUAL" while BLOCKED
    blocked_by_availability_id: ObjectId | None = None
