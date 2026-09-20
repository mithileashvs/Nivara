from datetime import date

from pydantic import ConfigDict, Field, model_validator

from app.models.enums import AppointmentStatus, AvailabilityStatus, SlotStatus
from app.schemas.common import RequestModel, ResponseModel, UTCDateTime, WholeMinuteTime
from app.utils.object_id import ObjectIdStr


class AvailabilityCreate(RequestModel):
    """A working window (generates slots) or a blocked period (time off)."""

    hospital_id: ObjectIdStr
    department_id: ObjectIdStr
    date: date
    start_time: WholeMinuteTime
    end_time: WholeMinuteTime
    slot_duration: int = Field(default=30, ge=10, le=120, description="Minutes per slot (multiple of 5)")
    status: AvailabilityStatus = AvailabilityStatus.WORKING
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _check(self) -> "AvailabilityCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.slot_duration % 5:
            raise ValueError("slot_duration must be a multiple of 5 minutes")
        return self


class AvailabilityOut(ResponseModel):
    id: str
    doctor_id: str
    hospital_id: str
    department_id: str
    date: str
    start_time: str
    end_time: str
    slot_duration: int
    status: AvailabilityStatus
    note: str | None = None


class AvailabilityCreateResponse(AvailabilityOut):
    """The created window's own fields (including `id`), flattened alongside the slot-generation
    stats — the doctor gets the window they just created plus what it did, in one shape."""

    slots_created: int = 0
    slots_blocked: int = Field(default=0, description="Free slots turned BLOCKED by a blocked period")
    reserved_slots_unaffected: int = Field(
        default=0, description="HELD/BOOKED slots inside a blocked period — left untouched"
    )


class SlotSearchParams(RequestModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")  # used as query model: pagination params live beside it
    doctor_id: ObjectIdStr
    date_from: date | None = None
    date_to: date | None = None
    hospital_id: ObjectIdStr | None = None
    department_id: ObjectIdStr | None = None
    include_unavailable: bool = Field(
        default=False,
        description="Also return HELD/BOOKED/BLOCKED slots (shown with their status) so a full day schedule can be rendered",
    )


class SlotPublicOut(ResponseModel):
    id: str
    doctor_id: str
    hospital_id: str
    department_id: str
    date: str
    start_time: str
    end_time: str
    status: SlotStatus = Field(description="Effective status (an expired hold is reported as AVAILABLE)")
    bookable: bool = Field(description="Computed by the backend — true only if a new request would be accepted now")
    unavailable_reason: str | None = None


class SlotDoctorOut(SlotPublicOut):
    appointment_id: str | None = None
    held_until: UTCDateTime | None = None
    block_source: str | None = None


class SlotBlockRequest(RequestModel):
    reason: str | None = Field(default=None, max_length=200)


class SlotDoctorSearchParams(RequestModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")  # used as query model: pagination params live beside it
    date_from: date | None = None
    date_to: date | None = None
    status: SlotStatus | None = None


__all__ = [
    "AvailabilityCreate", "AvailabilityOut", "AvailabilityCreateResponse", "SlotSearchParams",
    "SlotPublicOut", "SlotDoctorOut", "SlotBlockRequest", "SlotDoctorSearchParams", "AppointmentStatus",
]
