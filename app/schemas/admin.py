from pydantic import EmailStr, Field, field_validator

from app.schemas.auth import PHONE_PATTERN, validate_password_strength
from app.schemas.common import RequestModel, ResponseModel, UTCDateTime
from app.utils.object_id import ObjectIdStr


class AdminUserCreate(RequestModel):
    """Create an admin. Omit `managed_hospital_ids` for a platform-wide admin, or pass a list
    to create a hospital administrator limited to those hospitals."""

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    managed_hospital_ids: list[ObjectIdStr] | None = Field(default=None, max_length=50)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("email")
    @classmethod
    def _email_lower(cls, v: str) -> str:
        return v.lower()


class UserActiveUpdate(RequestModel):
    is_active: bool


class AdminScopeUpdate(RequestModel):
    managed_hospital_ids: list[ObjectIdStr] | None = Field(default=None, max_length=50)


class RoutingRuleCreate(RequestModel):
    department_name: str = Field(min_length=2, max_length=80)
    keywords: list[str] = Field(min_length=1, max_length=100)
    weight: float = Field(default=1.0, gt=0, le=100)
    is_emergency: bool = False
    is_active: bool = True

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, v: list[str]) -> list[str]:
        cleaned = [k.strip() for k in v if k and k.strip()]
        if not cleaned or any(len(k) > 60 for k in cleaned):
            raise ValueError("keywords must be non-empty strings of at most 60 characters")
        return cleaned


class RoutingRuleUpdate(RequestModel):
    department_name: str | None = Field(default=None, min_length=2, max_length=80)
    keywords: list[str] | None = Field(default=None, min_length=1, max_length=100)
    weight: float | None = Field(default=None, gt=0, le=100)
    is_emergency: bool | None = None
    is_active: bool | None = None


class RoutingRuleOut(ResponseModel):
    id: str
    department_name: str
    keywords: list[str]
    weight: float
    is_emergency: bool
    is_active: bool
    created_at: UTCDateTime
    updated_at: UTCDateTime


class MaintenanceResult(ResponseModel):
    expired_holds: int
    reminders_sent: int
    waitlist_entries_expired: int


class AdminStatistics(ResponseModel):
    """Basic platform counts, all computed live from the database. Never estimated."""

    total_users: int
    total_patients: int
    total_doctors: int
    total_hospitals: int
    total_departments: int
    total_appointments: int
    requested_appointments: int
    confirmed_appointments: int
    completed_appointments: int
    rejected_appointments: int
    cancelled_appointments: int
    no_show_appointments: int
