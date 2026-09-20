from bson import ObjectId
from pydantic import Field, model_validator

from app.models.base import MongoModel
from app.models.enums import Gender, IntakeStatus, ProfileStatus, UserRole
from app.utils.text import normalize


class User(MongoModel):
    name: str
    email: str
    password_hash: str
    phone: str | None = None
    role: UserRole
    is_active: bool = True
    # ADMIN only. None => platform-wide admin. A list => "hospital administrator"
    # limited to those hospitals (this is how hospital management is modelled
    # without adding a fourth authentication role).
    managed_hospital_ids: list[ObjectId] | None = None


class Patient(MongoModel):
    user_id: ObjectId
    date_of_birth: str | None = None  # "YYYY-MM-DD"
    gender: Gender = Gender.UNDISCLOSED
    basic_information: dict = Field(default_factory=dict)


class Doctor(MongoModel):
    user_id: ObjectId
    name: str
    specialty: str
    specialty_normalized: str = ""
    department_ids: list[ObjectId] = Field(default_factory=list)
    hospital_ids: list[ObjectId] = Field(default_factory=list)
    experience: int = 0  # years
    consultation_fee: float = 0.0
    consultation_types: list[str] = Field(default_factory=list)
    availability_status: IntakeStatus = IntakeStatus.OPEN  # doctor-level intake control
    profile_status: ProfileStatus = ProfileStatus.PENDING
    rating_sum: int = 0
    rating_count: int = 0

    @model_validator(mode="after")
    def _normalize(self) -> "Doctor":
        self.specialty_normalized = normalize(self.specialty)
        return self
