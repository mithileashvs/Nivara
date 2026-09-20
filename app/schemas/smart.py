from datetime import date

from pydantic import ConfigDict, BaseModel, Field, field_validator

from app.schemas.common import Page, RequestModel, ResponseModel, WholeMinuteTime
from app.models.enums import ConsultationType
from app.utils.object_id import ObjectIdStr

DISCLAIMER = (
    "SmartCare only helps you find the right department and book an appointment. It does not diagnose "
    "conditions, predict diseases, prescribe medicines, recommend dosages or suggest treatment. "
    "Please consult a qualified doctor for any medical concern. If you think you are having a medical "
    "emergency, contact your local emergency services immediately."
)


class DepartmentSuggestionRequest(RequestModel):
    symptoms: list[str] = Field(min_length=1, max_length=20, examples=[["headache", "fever"]])
    hospital_id: ObjectIdStr | None = Field(
        default=None, description="Optionally restrict the returned real departments to one hospital"
    )

    @field_validator("symptoms")
    @classmethod
    def _each(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s and s.strip()]
        if not cleaned:
            raise ValueError("at least one non-empty symptom is required")
        if any(len(s) > 80 for s in cleaned):
            raise ValueError("each symptom must be at most 80 characters")
        return cleaned


class SuggestedDepartment(BaseModel):
    department_name: str
    score: float
    matched_symptoms: list[str]
    explanation: str


class BookableDepartment(BaseModel):
    department_id: str
    hospital_id: str
    hospital_name: str
    name: str
    appointment_intake_status: str


class IgnoredInput(BaseModel):
    input: str
    reason: str


class DepartmentSuggestionResponse(BaseModel):
    primary_department: str
    suggested_departments: list[SuggestedDepartment]
    explanation: str
    unmatched_symptoms: list[str]
    ignored_inputs: list[IgnoredInput]
    available_departments: list[BookableDepartment] = Field(
        description="Real departments (currently accepting requests) matching the suggested names"
    )
    emergency_notice: str | None = None
    disclaimer: str = DISCLAIMER


class MatchCriteria(RequestModel):
    """Appointment-discovery criteria. This is NOT a medical recommendation."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")  # used as query model: pagination params live beside it

    doctor_id: ObjectIdStr | None = None
    specialty: str | None = Field(default=None, max_length=80)
    department_id: ObjectIdStr | None = None
    hospital_id: ObjectIdStr | None = Field(default=None, description="Hard filter")
    preferred_hospital_ids: list[ObjectIdStr] = Field(default_factory=list, max_length=10, description="Soft preference")
    consultation_type: ConsultationType | None = None
    city: str | None = Field(default=None, max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    max_distance_km: float | None = Field(default=None, gt=0, le=500)
    date_from: date | None = None
    date_to: date | None = None
    preferred_time_from: WholeMinuteTime | None = None
    preferred_time_to: WholeMinuteTime | None = None


class ScoreComponent(BaseModel):
    factor: str
    weight: float
    achieved: float = Field(ge=0, le=1)
    points: float
    detail: str


class SlotOption(BaseModel):
    slot_id: str
    doctor_id: str
    hospital_id: str
    department_id: str
    date: str
    start_time: str
    end_time: str


class DoctorMatchOut(BaseModel):
    doctor_id: str
    doctor_name: str
    specialty: str
    hospital_ids: list[str]
    consultation_fee: float
    match_score: float = Field(description="0-100, sum of the listed score_breakdown points")
    match_factors: list[str]
    score_breakdown: list[ScoreComponent]
    next_available: SlotOption | None = None
    upcoming_slots: list[SlotOption]


class DoctorMatchPage(Page[DoctorMatchOut]):
    criteria_applied: dict
    disclaimer: str = DISCLAIMER


class AppointmentOptionOut(BaseModel):
    slot: SlotOption
    doctor_name: str
    specialty: str
    hospital_name: str
    department_name: str
    match_score: float
    match_factors: list[str]
    score_breakdown: list[ScoreComponent]


class AppointmentOptionsPage(Page[AppointmentOptionOut]):
    criteria_applied: dict
    disclaimer: str = DISCLAIMER


__all__ = [n for n in dir() if not n.startswith("_")]
