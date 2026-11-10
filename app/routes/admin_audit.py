"""Phase 6 Centralized Audit Logs & Security Activity Router."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import DB, AdminUser, SettingsDep
from app.models.enums import AuditSeverity
from app.routes.docs import errs
from app.schemas.audit import AuditLogOut, SecurityActivityOut
from app.schemas.common import Page, make_page
from app.services.audit_service import AuditService
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/audit-logs",
    response_model=Page[AuditLogOut],
    summary="Query centralized append-only audit logs",
    description=(
        "Search and filter operational and security audit events. "
        "Hospital-scoped admins (`managed_hospital_ids`) are strictly restricted to their assigned hospitals. "
        "**Auth:** ADMIN (platform-wide or hospital-scoped)."
    ),
    responses=errs(400, 401, 403, 422),
)
async def list_audit_logs(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    q: str | None = Query(default=None, max_length=120, description="Search actor, description, action, entity or IP"),
    actor_role: str | None = Query(default=None, max_length=50),
    action: str | None = Query(default=None, max_length=250, description="Action or comma-separated actions"),
    entity_type: str | None = Query(default=None, max_length=80),
    entity_id: str | None = Query(default=None, max_length=120),
    hospital_id: str | None = Query(default=None, max_length=64),
    severity: AuditSeverity | None = None,
    actor_id: str | None = Query(default=None, max_length=64),
    date_from: date | None = None,
    date_to: date | None = None,
) -> Any:
    items, total = await AuditService(db, settings).list_audit_logs(
        admin,
        params,
        q=q,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        hospital_id=hospital_id,
        severity=severity.value if severity else None,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )
    return make_page(items, total, params.page, params.page_size)


@router.get(
    "/audit-logs/export",
    summary="Export filtered audit logs to CSV",
    description=(
        "Streams sanitized audit records matching the current filters as UTF-8 CSV. "
        "Enforces hospital scope identically to `GET /admin/audit-logs`. **Auth:** ADMIN."
    ),
    responses=errs(400, 401, 403, 422),
)
async def export_audit_logs(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    q: str | None = Query(default=None, max_length=120),
    actor_role: str | None = Query(default=None, max_length=50),
    action: str | None = Query(default=None, max_length=250),
    entity_type: str | None = Query(default=None, max_length=80),
    entity_id: str | None = Query(default=None, max_length=120),
    hospital_id: str | None = Query(default=None, max_length=64),
    severity: AuditSeverity | None = None,
    actor_id: str | None = Query(default=None, max_length=64),
    date_from: date | None = None,
    date_to: date | None = None,
) -> StreamingResponse:
    csv_text = await AuditService(db, settings).export_audit_logs_csv(
        admin,
        q=q,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        hospital_id=hospital_id,
        severity=severity.value if severity else None,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )
    filename = f"nivara_audit_logs_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/audit-logs/{log_id}",
    response_model=AuditLogOut,
    summary="Inspect a single audit log entry",
    description="Returns full sanitized details and request metadata for one audit event. **Auth:** ADMIN.",
    responses=errs(400, 401, 403, 404, 422),
)
async def get_audit_log_detail(log_id: ObjectIdPath, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    return await AuditService(db, settings).get_audit_log(admin, log_id)


@router.get(
    "/security/activity",
    response_model=SecurityActivityOut,
    summary="Security activity summary and threshold alerts",
    description=(
        "Returns real database-computed security event counts, threshold breach alerts, top suspicious IP sources, "
        "and recent security events. Strictly scoped by `managed_hospital_ids` for hospital admins. **Auth:** ADMIN."
    ),
    responses=errs(400, 401, 403, 422),
)
async def get_security_activity(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours (1 to 720)"),
    hospital_id: str | None = Query(default=None, max_length=64),
) -> Any:
    return await AuditService(db, settings).get_security_activity(
        admin, hours=hours, hospital_id=hospital_id
    )
