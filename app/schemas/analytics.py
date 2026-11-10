"""Pydantic v2 response and query schemas for Phase 5 operational analytics."""
from typing import Any

from app.schemas.common import Page, ResponseModel


class AnalyticsPeriodMeta(ResponseModel):
    preset: str
    date_from: str
    date_to: str
    days: int
    granularity: str
    timezone: str
    previous_date_from: str
    previous_date_to: str


class MetricComparison(ResponseModel):
    current: int
    previous: int
    delta: int
    change_pct: float | None = None


class RateComparison(ResponseModel):
    current: float
    previous: float
    delta_points: float
    numerator: int
    denominator: int
    formula: str


class StatusSlice(ResponseModel):
    status: str
    label: str
    count: int
    percentage: float
    previous_count: int = 0


class ConsultationTypeSlice(ResponseModel):
    consultation_type: str
    label: str
    count: int
    percentage: float


class AppointmentTrendPoint(ResponseModel):
    bucket_date: str
    label: str
    total: int
    requested: int
    confirmed: int
    reschedule_requested: int
    completed: int
    rejected: int
    cancelled: int
    no_show: int
    completion_rate: float
    rejection_rate: float
    cancellation_rate: float
    no_show_rate: float


class PatientTrendPoint(ResponseModel):
    bucket_date: str
    label: str
    new_patients: int


class OverviewHighlights(ResponseModel):
    highest_volume_period: dict[str, Any] | None = None
    most_active_department: dict[str, Any] | None = None
    most_active_hospital: dict[str, Any] | None = None


class AnalyticsOverviewOut(ResponseModel):
    scope: str
    scope_note: str | None = None
    period: AnalyticsPeriodMeta
    total_appointments: MetricComparison
    requested_appointments: MetricComparison
    confirmed_appointments: MetricComparison
    reschedule_requested_appointments: MetricComparison
    completed_appointments: MetricComparison
    rejected_appointments: MetricComparison
    cancelled_appointments: MetricComparison
    no_show_appointments: MetricComparison
    completion_rate: RateComparison
    rejection_rate: RateComparison
    cancellation_rate: RateComparison
    no_show_rate: RateComparison
    total_registered_patients: int
    new_patients_in_period: MetricComparison
    active_doctors: int
    accessible_hospitals: int
    status_distribution: list[StatusSlice]
    appointment_trends: list[AppointmentTrendPoint]
    patient_registration_trends: list[PatientTrendPoint]
    highlights: OverviewHighlights
    formula_definitions: dict[str, str]


class AppointmentTrendsOut(ResponseModel):
    scope: str
    period: AnalyticsPeriodMeta
    trends: list[AppointmentTrendPoint]
    summary_table: Page[AppointmentTrendPoint]
    formula_definitions: dict[str, str]


class AppointmentStatusAnalyticsOut(ResponseModel):
    scope: str
    period: AnalyticsPeriodMeta
    total_appointments: MetricComparison
    status_distribution: list[StatusSlice]
    consultation_types: list[ConsultationTypeSlice]
    rates: dict[str, RateComparison]
    formula_definitions: dict[str, str]


class HospitalAnalyticsRow(ResponseModel):
    hospital_id: str
    hospital_name: str
    city: str | None = None
    intake_status: str
    department_count: int
    active_doctor_count: int
    total_appointments: int
    requested_appointments: int
    confirmed_appointments: int
    reschedule_requested_appointments: int
    completed_appointments: int
    rejected_appointments: int
    cancelled_appointments: int
    no_show_appointments: int
    completion_rate: float
    rejection_rate: float
    cancellation_rate: float
    no_show_rate: float


class HospitalAnalyticsListOut(ResponseModel):
    scope: str
    period: AnalyticsPeriodMeta
    hospitals: Page[HospitalAnalyticsRow]
    formula_definitions: dict[str, str]


class DepartmentAnalyticsRow(ResponseModel):
    department_id: str
    department_name: str
    hospital_id: str
    hospital_name: str
    status: str
    intake_status: str
    doctor_count: int
    total_appointments: int
    requested_appointments: int
    confirmed_appointments: int
    reschedule_requested_appointments: int
    completed_appointments: int
    rejected_appointments: int
    cancelled_appointments: int
    no_show_appointments: int
    completion_rate: float
    rejection_rate: float
    cancellation_rate: float
    no_show_rate: float


class HospitalAnalyticsDetailOut(ResponseModel):
    scope: str
    period: AnalyticsPeriodMeta
    hospital: HospitalAnalyticsRow
    total_appointments_comparison: MetricComparison
    completed_comparison: MetricComparison
    completion_rate: RateComparison
    trends: list[AppointmentTrendPoint]
    departments: list[DepartmentAnalyticsRow]
    formula_definitions: dict[str, str]


class DepartmentAnalyticsListOut(ResponseModel):
    scope: str
    period: AnalyticsPeriodMeta
    summary: dict[str, Any]
    departments: Page[DepartmentAnalyticsRow]
    trends: list[AppointmentTrendPoint]
    formula_definitions: dict[str, str]


class DoctorAnalyticsRow(ResponseModel):
    doctor_id: str
    doctor_name: str
    specialty: str
    profile_status: str
    availability_status: str
    total_appointments: int
    requested_appointments: int
    confirmed_appointments: int
    reschedule_requested_appointments: int
    completed_appointments: int
    rejected_appointments: int
    cancelled_appointments: int
    no_show_appointments: int
    completion_rate: float
    rejection_rate: float
    cancellation_rate: float
    no_show_rate: float
    total_slots: int
    available_slots: int
    held_slots: int
    booked_slots: int
    blocked_slots: int


class DoctorAnalyticsListOut(ResponseModel):
    scope: str
    period: AnalyticsPeriodMeta
    summary: dict[str, Any]
    doctors: Page[DoctorAnalyticsRow]
    trends: list[AppointmentTrendPoint]
    formula_definitions: dict[str, str]


class PatientActivityTrendPoint(ResponseModel):
    bucket_date: str
    label: str
    new_registrations: int
    active_patients: int
    appointments: int


class PatientAnalyticsOut(ResponseModel):
    scope: str
    scope_note: str | None = None
    period: AnalyticsPeriodMeta
    total_registered_patients: int
    new_registrations: MetricComparison
    active_patients: MetricComparison
    returning_patients: int
    single_visit_active_patients: int
    returning_rate: float
    trends: list[PatientActivityTrendPoint]
    formula_definitions: dict[str, str]
