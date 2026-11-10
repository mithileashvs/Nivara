from datetime import date, datetime
from typing import Any

from pydantic import Field

from app.models.enums import AuditSeverity
from app.schemas.auth import UserOut
from app.schemas.common import RequestModel, ResponseModel, UTCDateTime
from app.utils.object_id import ObjectIdStr


class AuditLogOut(ResponseModel):
    id: str
    actor_id: str | None = None
    actor_role: str
    actor_name: str | None = None
    actor_email: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    hospital_id: str | None = None
    hospital_name: str | None = None
    severity: AuditSeverity = AuditSeverity.INFO
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: UTCDateTime


class SecurityThresholdsOut(ResponseModel):
    failed_login_burst_threshold: int
    unauthorized_spike_threshold: int
    medical_unauthorized_threshold: int
    high_download_volume_threshold: int


class SecuritySummaryOut(ResponseModel):
    failed_logins: int
    unauthorized_attempts: int
    forbidden_attempts: int
    medical_unauthorized_attempts: int
    admin_scope_and_status_changes: int
    doctor_verification_changes: int
    security_alerts_triggered: int


class SecurityAlertOut(ResponseModel):
    code: str
    severity: AuditSeverity
    title: str
    description: str
    count: int
    threshold: int
    source: str | None = None
    latest_at: UTCDateTime | None = None


class SuspiciousSourceOut(ResponseModel):
    ip_address: str
    count: int
    latest_at: UTCDateTime | None = None
    actions: list[str] = Field(default_factory=list)


class SecurityActivityOut(ResponseModel):
    window_hours: int
    since: UTCDateTime
    is_platform_scope: bool
    summary: SecuritySummaryOut
    thresholds: SecurityThresholdsOut
    alerts: list[SecurityAlertOut]
    suspicious_sources: list[SuspiciousSourceOut]
    recent_security_events: list[AuditLogOut]


class UserStatusUpdate(RequestModel):
    is_active: bool
    reason: str | None = Field(default=None, max_length=300)


class AdminUserProfileSummaryOut(ResponseModel):
    profile_id: str | None = None
    specialty: str | None = None
    profile_status: str | None = None
    availability_status: str | None = None
    experience: int | None = None
    consultation_fee: float | None = None
    rating_average: float | None = None
    rating_count: int | None = None
    hospital_ids: list[str] = Field(default_factory=list)
    department_ids: list[str] = Field(default_factory=list)
    managed_hospitals: list[dict[str, str]] = Field(default_factory=list)


class AdminUserDetailOut(ResponseModel):
    user: UserOut
    profile_summary: AdminUserProfileSummaryOut
    recent_activity: list[AuditLogOut]


class AdminHospitalOut(ResponseModel):
    id: str
    name: str
    address: str
    location: dict[str, Any] = Field(default_factory=dict)
    contact: dict[str, Any] = Field(default_factory=dict)
    appointment_intake_status: str
    department_ids: list[str] = Field(default_factory=list)
    department_count: int = 0
    active_doctor_count: int = 0
    active_appointments_count: int = 0
    created_at: UTCDateTime
    updated_at: UTCDateTime


class AdminDoctorVerificationCountsOut(ResponseModel):
    pending: int
    active: int
    suspended: int
    total: int


class AdminDoctorVerificationItemOut(ResponseModel):
    id: str
    user_id: str
    name: str
    email: str | None = None
    phone: str | None = None
    specialty: str
    experience: int
    consultation_fee: float
    consultation_types: list[str] = Field(default_factory=list)
    profile_status: str
    availability_status: str
    hospital_ids: list[str] = Field(default_factory=list)
    department_ids: list[str] = Field(default_factory=list)
    hospital_names: list[str] = Field(default_factory=list)
    department_names: list[str] = Field(default_factory=list)
    latest_verification_reason: str | None = None
    latest_verification_at: UTCDateTime | None = None
    rating_average: float | None = None
    rating_count: int = 0
    created_at: UTCDateTime
    updated_at: UTCDateTime


class AdminDoctorVerificationPageOut(ResponseModel):
    items: list[AdminDoctorVerificationItemOut]
    total: int
    page: int
    page_size: int
    total_pages: int
    counts: AdminDoctorVerificationCountsOut
