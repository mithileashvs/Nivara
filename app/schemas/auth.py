from datetime import date

from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.models.enums import ConsultationType, Gender, UserRole
from app.schemas.common import RequestModel, ResponseModel, UTCDateTime

PHONE_PATTERN = r"^\+?[0-9][0-9\- ]{6,18}$"


def validate_password_strength(value: str) -> str:
    if len(value) < 8:
        raise ValueError("password must be at least 8 characters")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("password must contain at least one letter and one digit")
    return value


class RegisterRequest(RequestModel):
    """Self-registration for patients and doctors. Admin accounts cannot be self-registered."""

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    role: UserRole

    # patient profile (optional)
    date_of_birth: date | None = None
    gender: Gender | None = None

    # doctor profile (specialty required when role == DOCTOR)
    specialty: str | None = Field(default=None, min_length=2, max_length=80)
    experience: int = Field(default=0, ge=0, le=70, description="Years of experience")
    consultation_fee: float = Field(default=0.0, ge=0, le=1_000_000)
    consultation_types: list[ConsultationType] | None = None

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("email")
    @classmethod
    def _email_lower(cls, v: str) -> str:
        return v.lower()

    @field_validator("role")
    @classmethod
    def _no_admin(cls, v: UserRole) -> UserRole:
        if v == UserRole.ADMIN:
            raise ValueError("admin accounts cannot be self-registered")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date | None) -> date | None:
        if v is not None and (v > date.today() or v.year < 1900):
            raise ValueError("date_of_birth must be a valid past date")
        return v

    @model_validator(mode="after")
    def _role_fields(self) -> "RegisterRequest":
        if self.role == UserRole.DOCTOR and not self.specialty:
            raise ValueError("specialty is required for doctor registration")
        return self


class LoginRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email_lower(cls, v: str) -> str:
        return v.lower()


class UserOut(ResponseModel):
    id: str
    name: str
    email: EmailStr
    phone: str | None = None
    role: UserRole
    is_active: bool
    managed_hospital_ids: list[str] | None = Field(
        default=None, description="ADMIN only. null = platform-wide admin; list = hospital-scoped admin."
    )
    created_at: UTCDateTime
    updated_at: UTCDateTime


class TokenResponse(ResponseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until the token expires")
    user: UserOut


class OAuth2TokenResponse(ResponseModel):
    """Minimal OAuth2 password-flow response (used by Swagger's Authorize button)."""

    access_token: str
    token_type: str = "bearer"
