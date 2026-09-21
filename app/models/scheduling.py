from datetime import datetime

from app.models.base import EntityModel
from app.models.enums import AvailabilityStatus, SlotStatus


class DoctorAvailability(EntityModel):
    doctor_id: str
    hospital_id: str
    department_id: str
    date: str  # "YYYY-MM-DD" (clinic-local)
    start_time: str  # "HH:MM"
    end_time: str
    slot_duration: int  # minutes
    status: AvailabilityStatus = AvailabilityStatus.WORKING
    note: str | None = None


class AppointmentSlot(EntityModel):
    doctor_id: str
    hospital_id: str
    department_id: str
    date: str
    start_time: str
    end_time: str
    start_at: datetime  # naive UTC
    end_at: datetime  # naive UTC
    status: SlotStatus = SlotStatus.AVAILABLE
    appointment_id: str | None = None
    held_until: datetime | None = None
    availability_id: str | None = None  # working window that generated the slot
    block_source: str | None = None  # "AVAILABILITY" | "MANUAL" while BLOCKED
    blocked_by_availability_id: str | None = None
