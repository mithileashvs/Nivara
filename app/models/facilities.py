from pydantic import Field, model_validator

from app.models.base import EntityModel
from app.models.enums import DepartmentStatus, IntakeStatus
from app.utils.text import normalize


class Hospital(EntityModel):
    name: str
    name_normalized: str = ""
    address: str
    location: dict = Field(default_factory=dict)  # {city, state, latitude, longitude}
    contact: dict = Field(default_factory=dict)  # {phone, email, website}
    appointment_intake_status: IntakeStatus = IntakeStatus.OPEN
    department_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize(self) -> "Hospital":
        self.name_normalized = normalize(self.name)
        if self.location.get("city"):
            self.location = {**self.location, "city_normalized": normalize(self.location["city"])}
        return self


class Department(EntityModel):
    hospital_id: str
    name: str
    name_normalized: str = ""
    description: str | None = None
    status: DepartmentStatus = DepartmentStatus.ACTIVE
    appointment_intake_status: IntakeStatus = IntakeStatus.OPEN

    @model_validator(mode="after")
    def _normalize(self) -> "Department":
        self.name_normalized = normalize(self.name)
        return self
