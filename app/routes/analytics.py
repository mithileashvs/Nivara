"""Phase 5 Operational Healthcare Analytics Router."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import DB, AdminUser, SettingsDep
from app.models.enums import (
    AnalyticsGranularity,
    AnalyticsPreset,
    AnalyticsReportType,
    AppointmentStatus,
)
from app.routes.docs import errs
from app.schemas.analytics import (
    AnalyticsOverviewOut,
    AppointmentStatusAnalyticsOut,
    AppointmentTrendsOut,
    DepartmentAnalyticsListOut,
    DoctorAnalyticsListOut,
    HospitalAnalyticsDetailOut,
    HospitalAnalyticsListOut,
    PatientAnalyticsOut,
)
from app.services.analytics_service import AnalyticsService
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@dataclass(frozen=True)
class AnalyticsFilters:
    preset: AnalyticsPreset
    date_from: str | None
    date_to: str | None
    granularity: AnalyticsGranularity
    hospital_id: str | None
    department_id: str | None
    doctor_id: str | None
    status: AppointmentStatus | None


def analytics_filters(
    preset: AnalyticsPreset = Query(
        AnalyticsPreset.LAST_30_DAYS,
        description="Date range preset (overridden if custom date_from/date_to are supplied).",
    ),
    date_from: str | None = Query(
        default=None,
        description="Custom inclusive start date (YYYY-MM-DD).",
    ),
    date_to: str | None = Query(
        default=None,
        description="Custom inclusive end date (YYYY-MM-DD).",
    ),
    granularity: AnalyticsGranularity = Query(
        AnalyticsGranularity.DAILY,
        description="Time-series grouping granularity (`daily`, `weekly`, `monthly`).",
    ),
    hospital_id: str | None = Query(
        default=None,
        description="Filter by hospital UUID (enforced against admin managed_hospital_ids).",
    ),
    department_id: str | None = Query(
        default=None,
        description="Filter by department UUID (enforced against admin managed_hospital_ids).",
    ),
    doctor_id: str | None = Query(
        default=None,
        description="Filter by doctor UUID (enforced against admin managed_hospital_ids).",
    ),
    status: AppointmentStatus | None = Query(
        default=None,
        description="Filter by appointment status.",
    ),
) -> AnalyticsFilters:
    return AnalyticsFilters(
        preset=preset,
        date_from=(date_from or "").strip() or None,
        date_to=(date_to or "").strip() or None,
        granularity=granularity,
        hospital_id=(hospital_id or "").strip() or None,
        department_id=(department_id or "").strip() or None,
        doctor_id=(doctor_id or "").strip() or None,
        status=status,
    )


async def _prepare(
    admin: dict,
    db: Any,
    settings: Any,
    f: AnalyticsFilters,
):
    svc = AnalyticsService(db, settings)
    period = svc.resolve_period(
        preset=f.preset,
        date_from=f.date_from,
        date_to=f.date_to,
        granularity=f.granularity,
    )
    scope = await svc.resolve_scope(
        admin,
        hospital_id=f.hospital_id,
        department_id=f.department_id,
        doctor_id=f.doctor_id,
        status=f.status,
    )
    return svc, scope, period


@router.get(
    "/overview",
    response_model=AnalyticsOverviewOut,
    summary="Operational analytics overview",
    description=(
        "KPI metrics with previous-period comparisons, status breakdown, appointment & registration trends, "
        "and real data highlights. **Auth:** ADMIN (platform or hospital-scoped)."
    ),
    responses=errs(400, 401, 403, 404, 422),
)
async def analytics_overview(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    f: Annotated[AnalyticsFilters, Depends(analytics_filters)],
) -> Any:
    svc, scope, period = await _prepare(admin, db, settings, f)
    return await svc.get_overview(scope, period)


@router.get(
    "/appointments/trends",
    response_model=AppointmentTrendsOut,
    summary="Appointment volume trends & period summary table",
    description=(
        "Daily, weekly, or monthly appointment counts, rates, and paginated chronological summary table. "
        "**Auth:** ADMIN (platform or hospital-scoped)."
    ),
    responses=errs(400, 401, 403, 404, 422),
)
async def appointment_trends(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    f: Annotated[AnalyticsFilters, Depends(analytics_filters)],
    params: Annotated[PageParams, Depends(page_params)],
) -> Any:
    svc, scope, period = await _prepare(admin, db, settings, f)
    return await svc.get_appointment_trends_and_summary(scope, period, params)


@router.get(
    "/appointments/status",
    response_model=AppointmentStatusAnalyticsOut,
    summary="Appointment status distribution & consultation types",
    description=(
        "Detailed appointment status slices, previous-period comparison, consultation-type breakdown, and rates. "
        "**Auth:** ADMIN (platform or hospital-scoped)."
    ),
    responses=errs(400, 401, 403, 404, 422),
)
async def appointment_status_analytics(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    f: Annotated[AnalyticsFilters, Depends(analytics_filters)],
) -> Any:
    svc, scope, period = await _prepare(admin, db, settings, f)
    return await svc.get_appointment_status_analytics(scope, period)


@router.get(
    "/hospitals",
    response_model=HospitalAnalyticsListOut,
    summary="Hospital performance & volume comparison",
    description=(
        "Hospital-wise appointment volume, status counts, rates, department count, and active doctors. "
        "**Auth:** ADMIN (platform or hospital-scoped)."
    ),
    responses=errs(400, 401, 403, 404, 422),
)
async def hospital_analytics_list(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    f: Annotated[AnalyticsFilters, Depends(analytics_filters)],
    params: Annotated[PageParams, Depends(page_params)],
    search: str | None = Query(default=None, max_length=100, description="Filter hospitals by name."),
) -> Any:
    svc, scope, period = await _prepare(admin, db, settings, f)
    return await svc.get_hospital_analytics(scope, period, params, search=(search or "").strip() or None)


@router.get(
    "/hospitals/{hospital_id}",
    response_model=HospitalAnalyticsDetailOut,
    summary="Detailed analytics for a specific hospital",
    description=(
        "Hospital KPIs with previous-period comparison, time-series trends, and department breakdown. "
        "Strictly enforces `managed_hospital_ids` authorization. **Auth:** ADMIN."
    ),
    responses=errs(400, 401, 403, 404, 422),
)
async def hospital_analytics_detail(
    hospital_id: ObjectIdPath,
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    preset: AnalyticsPreset = Query(AnalyticsPreset.LAST_30_DAYS),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    granularity: AnalyticsGranularity = Query(AnalyticsGranularity.DAILY),
    department_id: str | None = Query(default=None),
    doctor_id: str | None = Query(default=None),
    status: AppointmentStatus | None = Query(default=None),
) -> Any:
    svc = AnalyticsService(db, settings)
    period = svc.resolve_period(
        preset=preset,
        date_from=(date_from or "").strip() or None,
        date_to=(date_to or "").strip() or None,
        granularity=granularity,
    )
    return await svc.get_hospital_detail_analytics(
        admin,
        hospital_id,
        period,
        department_id=(department_id or "").strip() or None,
        doctor_id=(doctor_id or "").strip() or None,
        status=status,
    )


@router.get(
    "/departments",
    response_model=DepartmentAnalyticsListOut,
    summary="Department operational analytics",
    description=(
        "Department-wise appointment volume, status counts, rates, active doctor count, and overall trends. "
        "**Auth:** ADMIN (platform or hospital-scoped)."
    ),
    responses=errs(400, 401, 403, 404, 422),
)
async def department_analytics(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    f: Annotated[AnalyticsFilters, Depends(analytics_filters)],
    params: Annotated[PageParams, Depends(page_params)],
    search: str | None = Query(default=None, max_length=100, description="Filter by department or hospital name."),
) -> Any:
    svc, scope, period = await _prepare(admin, db, settings, f)
    return await svc.get_department_analytics(scope, period, params, search=(search or "").strip() or None)


@router.get(
    "/doctors",
    response_model=DoctorAnalyticsListOut,
    summary="Doctor workload & slot analytics",
    description=(
        "Doctor appointment volume, outcome rates, and actual slot breakdown from `appointment_slots`. "
        "Does not expose clinical scoring or synthetic efficiency indices. **Auth:** ADMIN (platform or hospital-scoped)."
    ),
    responses=errs(400, 401, 403, 404, 422),
)
async def doctor_analytics(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    f: Annotated[AnalyticsFilters, Depends(analytics_filters)],
    params: Annotated[PageParams, Depends(page_params)],
    search: str | None = Query(default=None, max_length=100, description="Filter doctors by name or specialty."),
) -> Any:
    svc, scope, period = await _prepare(admin, db, settings, f)
    return await svc.get_doctor_analytics(scope, period, params, search=(search or "").strip() or None)


@router.get(
    "/patients",
    response_model=PatientAnalyticsOut,
    summary="Aggregate patient growth & engagement analytics (no PII)",
    description=(
        "Total registered patients, new registrations, active patients, returning vs single-visit patients, and trends. "
        "Strictly aggregate counts only — never returns patient PII. **Auth:** ADMIN (platform or hospital-scoped)."
    ),
    responses=errs(400, 401, 403, 404, 422),
)
async def patient_analytics(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    f: Annotated[AnalyticsFilters, Depends(analytics_filters)],
) -> Any:
    svc, scope, period = await _prepare(admin, db, settings, f)
    return await svc.get_patient_analytics(scope, period)


@router.get(
    "/reports/export",
    summary="Export operational analytics report as CSV",
    description=(
        "Generates and downloads a sanitized CSV report (`appointment_summary`, `hospital_performance`, "
        "`department_performance`, `doctor_statistics`, `patient_registrations`) using the exact active filters "
        "and backend authorization scope. Never exports patient PII."
    ),
    responses=errs(400, 401, 403, 404, 422),
)
async def export_analytics_report(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    f: Annotated[AnalyticsFilters, Depends(analytics_filters)],
    report_type: AnalyticsReportType = Query(
        AnalyticsReportType.APPOINTMENT_SUMMARY,
        description="Report dataset to export as CSV.",
    ),
) -> StreamingResponse:
    svc, scope, period = await _prepare(admin, db, settings, f)
    csv_text, filename = await svc.export_csv_report(report_type, scope, period)
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
