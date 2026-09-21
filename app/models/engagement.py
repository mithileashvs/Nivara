from pydantic import Field, model_validator

from app.models.base import EntityModel
from app.models.enums import WaitlistStatus
from app.utils.text import normalize


class Notification(EntityModel):
    user_id: str
    type: str
    title: str
    message: str
    related_appointment_id: str | None = None
    is_read: bool = False
    data: dict = Field(default_factory=dict)


class WaitlistEntry(EntityModel):
    patient_id: str
    patient_user_id: str
    doctor_id: str | None = None
    department_id: str | None = None
    hospital_id: str | None = None
    specialty: str | None = None
    specialty_normalized: str | None = None
    date_from: str
    date_to: str
    time_from: str | None = None
    time_to: str | None = None
    consultation_type: str | None = None
    existing_appointment_id: str | None = None
    status: WaitlistStatus = WaitlistStatus.ACTIVE
    notified_slot_ids: list[str] = Field(default_factory=list)
    fulfilled_appointment_id: str | None = None

    @model_validator(mode="after")
    def _normalize(self) -> "WaitlistEntry":
        self.specialty_normalized = normalize(self.specialty) if self.specialty else None
        return self


class SymptomRoutingRule(EntityModel):
    department_name: str
    department_name_normalized: str = ""
    keywords: list[str]
    weight: float = 1.0
    is_emergency: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def _normalize(self) -> "SymptomRoutingRule":
        self.department_name_normalized = normalize(self.department_name)
        self.keywords = sorted({normalize(k) for k in self.keywords if normalize(k)})
        return self
