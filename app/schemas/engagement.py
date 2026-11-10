from datetime import date

from pydantic import Field, model_validator

from app.models.enums import ConsultationType, NotificationType, WaitlistOfferStatus, WaitlistStatus
from app.schemas.common import RequestModel, ResponseModel, UTCDateTime, WholeMinuteTime
from app.utils.object_id import ObjectIdStr


class NotificationOut(ResponseModel):
    id: str
    user_id: str
    type: NotificationType
    title: str
    message: str
    category: str = "APPOINTMENT"
    action_url: str | None = None
    related_appointment_id: str | None = None
    is_read: bool
    read_at: UTCDateTime | None = None
    data: dict = Field(default_factory=dict)
    created_at: UTCDateTime


class UnreadCountOut(ResponseModel):
    unread: int


class NotificationPreferencesOut(ResponseModel):
    appointment_updates: bool = True
    rescheduling_updates: bool = True
    cancellation_updates: bool = True
    waitlist_updates: bool = True
    system_announcements: bool = True
    categories: dict[str, bool] = Field(default_factory=dict)


class NotificationPreferencesUpdate(RequestModel):
    appointment_updates: bool | None = None
    rescheduling_updates: bool | None = None
    cancellation_updates: bool | None = None
    waitlist_updates: bool | None = None
    system_announcements: bool | None = None
    categories: dict[str, bool] | None = None


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
    queue_position: int | None = None
    patients_ahead: int | None = None
    created_at: UTCDateTime
    updated_at: UTCDateTime


class WaitlistOfferOut(ResponseModel):
    id: str
    waitlist_entry_id: str
    patient_id: str
    doctor_id: str
    doctor_name: str | None = None
    hospital_id: str | None = None
    hospital_name: str | None = None
    department_id: str | None = None
    department_name: str | None = None
    slot_id: str | None = None
    appointment_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    status: WaitlistOfferStatus
    expires_at: UTCDateTime
    responded_at: UTCDateTime | None = None
    reason: str | None = None
    appointment_id: str | None = None
    created_at: UTCDateTime


class WaitlistOfferDecision(RequestModel):
    reason: str | None = Field(default=None, max_length=500)


class DoctorWaitlistStats(ResponseModel):
    active_waitlist_patients: int = 0
    pending_offers: int = 0
    fulfilled_entries: int = 0
    upcoming_waitlist_appointments: int = 0


class AdminWaitlistStats(ResponseModel):
    total_active_entries: int = 0
    pending_offers: int = 0
    fulfilled_entries: int = 0
    expired_offers: int = 0
    hospital_breakdown: dict[str, int] = Field(default_factory=dict)
    department_breakdown: dict[str, int] = Field(default_factory=dict)
    doctor_breakdown: dict[str, int] = Field(default_factory=dict)
