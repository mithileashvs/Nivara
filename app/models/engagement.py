from bson import ObjectId
from pydantic import Field, model_validator

from app.models.base import MongoModel
from app.models.enums import WaitlistStatus
from app.utils.text import normalize


class Notification(MongoModel):
    user_id: ObjectId
    type: str
    title: str
    message: str
    related_appointment_id: ObjectId | None = None
    is_read: bool = False
    data: dict = Field(default_factory=dict)


class WaitlistEntry(MongoModel):
    patient_id: ObjectId
    patient_user_id: ObjectId
    doctor_id: ObjectId | None = None
    department_id: ObjectId | None = None
    hospital_id: ObjectId | None = None
    specialty: str | None = None
    specialty_normalized: str | None = None
    date_from: str
    date_to: str
    time_from: str | None = None
    time_to: str | None = None
    consultation_type: str | None = None
    # "Notify me if an EARLIER appointment opens": only slots starting before this
    # existing appointment are eligible.
    existing_appointment_id: ObjectId | None = None
    status: WaitlistStatus = WaitlistStatus.ACTIVE
    notified_slot_ids: list[ObjectId] = Field(default_factory=list)
    fulfilled_appointment_id: ObjectId | None = None

    @model_validator(mode="after")
    def _normalize(self) -> "WaitlistEntry":
        self.specialty_normalized = normalize(self.specialty) if self.specialty else None
        return self


class SymptomRoutingRule(MongoModel):
    department_name: str
    department_name_normalized: str = ""
    keywords: list[str]
    weight: float = 1.0
    is_emergency: bool = False  # adds a "seek emergency care" notice — never a diagnosis
    is_active: bool = True

    @model_validator(mode="after")
    def _normalize(self) -> "SymptomRoutingRule":
        self.department_name_normalized = normalize(self.department_name)
        self.keywords = sorted({normalize(k) for k in self.keywords if normalize(k)})
        return self
