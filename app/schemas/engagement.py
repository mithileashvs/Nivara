from datetime import date

from pydantic import Field, model_validator

from app.models.enums import ConsultationType, NotificationType, WaitlistStatus
from app.schemas.common import RequestModel, ResponseModel, UTCDateTime, WholeMinuteTime
from app.utils.object_id import ObjectIdStr


class NotificationOut(ResponseModel):
    id: str
    user_id: str
    type: NotificationType
    title: str
    message: str
    related_appointment_id: str | None = None
    is_read: bool
    data: dict = Field(default_factory=dict)
    created_at: UTCDateTime


class UnreadCountOut(ResponseModel):
    unread: int


class WaitlistCreate(RequestModel):
    """"Notify me if a matching appointment opens up."  At least one of
    doctor / department / hospital / specialty is required."""

    doctor_id: ObjectIdStr | None = None
    department_id: ObjectIdStr | None = None
    hospital_id: ObjectIdStr | None = None
    specialty: str | None = Field(default=None, min_length=2, max_length=80)
    date_from: date
    date_to: date
    time_from: WholeMinuteTime | None = None
    time_to: WholeMinuteTime | None = None
    consultation_type: ConsultationType | None = None
    existing_appointment_id: ObjectIdStr | None = Field(
        default=None,
        description="If set, only slots EARLIER than this existing appointment qualify ('notify me of an earlier slot')",
    )

    @model_validator(mode="after")
    def _check(self) -> "WaitlistCreate":
        if not any([self.doctor_id, self.department_id, self.hospital_id, self.specialty]):
            raise ValueError("provide at least one of doctor_id, department_id, hospital_id or specialty")
        if self.date_to < self.date_from:
            raise ValueError("date_to must be on or after date_from")
        if (self.date_to - self.date_from).days > 90:
            raise ValueError("waitlist date range may not exceed 90 days")
        if self.time_from and self.time_to and self.time_to <= self.time_from:
            raise ValueError("time_to must be after time_from")
        return self


class WaitlistOut(ResponseModel):
    id: str
    patient_id: str
    doctor_id: str | None = None
    department_id: str | None = None
    hospital_id: str | None = None
    specialty: str | None = None
    date_from: str
    date_to: str
    time_from: str | None = None
    time_to: str | None = None
    consultation_type: str | None = None
    existing_appointment_id: str | None = None
    status: WaitlistStatus
    notified_slot_ids: list[str]
    fulfilled_appointment_id: str | None = None
    created_at: UTCDateTime
    updated_at: UTCDateTime
