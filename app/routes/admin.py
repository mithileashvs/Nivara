from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DB, AdminUser, SettingsDep
from app.models.enums import AuditAction, AuditEntityType, AuditSeverity, IntakeStatus, ProfileStatus, UserRole, WaitlistStatus
from app.routes.docs import errs
from app.schemas.admin import (
    AdminScopeUpdate,
    AdminStatistics,
    AdminUserCreate,
    MaintenanceResult,
    RoutingRuleCreate,
    RoutingRuleOut,
    RoutingRuleUpdate,
    UserActiveUpdate,
)
from app.schemas.appointments import AdminAppointmentOut, AdminAppointmentSearchParams
from app.schemas.audit import (
    AdminDoctorVerificationPageOut,
    AdminHospitalOut,
    AdminUserDetailOut,
    AuditLogOut,
    UserStatusUpdate,
)
from app.schemas.auth import UserOut
from app.schemas.common import Page, make_page
from app.schemas.engagement import AdminWaitlistStats, WaitlistOut
from app.schemas.users import DoctorAffiliationUpdate, DoctorOut, DoctorProfileStatusUpdate
from app.services.admin_service import AdminService, require_platform_admin
from app.services.appointment_service import AppointmentService
from app.services.audit_service import AuditService
from app.services.department_routing_service import DepartmentRoutingService
from app.services.doctor_service import DoctorService, doctor_view
from app.services.maintenance_service import MaintenanceService
from app.services.waitlist_service import WaitlistService
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/admin", tags=["Admin"])
NOTE = " Admins manage platform resources only — they never approve individual appointments."


@router.post(
    "/users",
    response_model=UserOut,
    status_code=201,
    summary="Create an admin user",
    description=(
        "Omit `managed_hospital_ids` for a platform admin; pass a list for a hospital administrator scoped to "
        "those hospitals. **Auth:** platform ADMIN." + NOTE
    ),
    responses=errs(400, 401, 403, 409, 422),
)
async def create_admin(payload: AdminUserCreate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    return to_api(await AdminService(db, settings).create_admin(payload, actor=admin))


@router.get(
    "/users",
    response_model=Page[UserOut],
    summary="List users",
    description="Filter by role / active flag / search query. **Auth:** platform ADMIN.",
    responses=errs(401, 403, 422),
)
async def list_users(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    role: UserRole | None = None,
    is_active: bool | None = None,
    q: str | None = Query(default=None, max_length=120, description="Search by name or email"),
) -> Any:
    require_platform_admin(admin)
    items, total = await AdminService(db, settings).list_users(params, role, is_active, q=q)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailOut,
    summary="Get user detail & recent operational activity",
    description="Returns non-clinical profile summary and recent audit events. **Auth:** platform ADMIN.",
    responses=errs(401, 403, 404, 422),
)
async def get_user_detail(user_id: ObjectIdPath, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    detail = await AdminService(db, settings).get_user_detail(user_id)
    return {
        "user": to_api(detail["user"]),
        "profile_summary": detail["profile_summary"],
        "recent_activity": detail["recent_activity"],
    }


@router.put(
    "/users/{user_id}/active",
    response_model=UserOut,
    summary="Activate or deactivate a user",
    description="Deactivated users lose access immediately. You cannot change your own status. **Auth:** platform ADMIN.",
    responses=errs(400, 401, 403, 404, 422),
)
async def set_active(user_id: ObjectIdPath, payload: UserActiveUpdate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    return to_api(await AdminService(db, settings).set_active(admin, user_id, payload.is_active))


@router.patch(
    "/users/{user_id}/status",
    response_model=UserOut,
    summary="Activate or deactivate a user with optional moderation reason",
    description="Updates active status, prevents self-deactivation, and writes an audit trail record. **Auth:** platform ADMIN.",
    responses=errs(400, 401, 403, 404, 422),
)
async def patch_user_status(
    user_id: ObjectIdPath, payload: UserStatusUpdate, admin: AdminUser, db: DB, settings: SettingsDep
) -> Any:
    require_platform_admin(admin)
    return to_api(await AdminService(db, settings).set_active(admin, user_id, payload.is_active, reason=payload.reason))


@router.put(
    "/users/{user_id}/hospital-scope",
    response_model=UserOut,
    summary="Set an admin's hospital scope",
    description="`null` = platform-wide; list = hospital administrator. **Auth:** platform ADMIN.",
    responses=errs(400, 401, 403, 404, 422),
)
async def set_scope(
    user_id: ObjectIdPath, payload: AdminScopeUpdate, admin: AdminUser, db: DB, settings: SettingsDep
) -> Any:
    require_platform_admin(admin)
    return to_api(await AdminService(db, settings).set_scope(user_id, payload.managed_hospital_ids, actor=admin))


@router.get(
    "/hospitals",
    response_model=Page[AdminHospitalOut],
    summary="List hospitals for administration",
    description=(
        "Hospital management view with live department, doctor, and active appointment counts. "
        "Hospital-scoped admins only see hospitals in `managed_hospital_ids`. **Auth:** ADMIN."
    ),
    responses=errs(401, 403, 422),
)
async def list_admin_hospitals(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    q: str | None = Query(default=None, max_length=120),
    city: str | None = Query(default=None, max_length=80),
    intake_status: IntakeStatus | None = None,
) -> Any:
    items, total = await AdminService(db, settings).list_hospitals_for_admin(
        admin, params, q=q, city=city, intake_status=intake_status
    )
    return make_page(items, total, params.page, params.page_size)


@router.get(
    "/doctors",
    response_model=Page[DoctorOut],
    summary="List doctor profiles (any status)",
    description="Use `profile_status=PENDING` to find doctors awaiting verification. **Auth:** platform ADMIN.",
    responses=errs(401, 403, 422),
)
async def list_doctors(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    profile_status: ProfileStatus | None = None,
    q: str | None = Query(default=None, max_length=120),
) -> Any:
    require_platform_admin(admin)
    items, total = await AdminService(db, settings).list_doctors_for_admin(
        params, profile_status=profile_status, q=q
    )
    return make_page([to_api(doctor_view(i)) for i in items], total, params.page, params.page_size)


@router.get(
    "/doctor-verification",
    response_model=AdminDoctorVerificationPageOut,
    summary="Doctor verification management queue",
    description=(
        "Lists doctor profiles grouped with live pending/active/suspended counts, affiliations, and latest "
        "verification reason from audit logs. **Auth:** platform ADMIN."
    ),
    responses=errs(401, 403, 422),
)
async def list_doctor_verification(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    profile_status: ProfileStatus | None = None,
    q: str | None = Query(default=None, max_length=120),
) -> Any:
    require_platform_admin(admin)
    return await AdminService(db, settings).list_doctor_verification(
        params, profile_status=profile_status, q=q
    )


@router.get(
    "/doctor-verification/{doctor_id}/history",
    response_model=list[AuditLogOut],
    summary="Doctor verification & affiliation audit history",
    description="Chronological verification and affiliation changes recorded in `audit_logs`. **Auth:** platform ADMIN.",
    responses=errs(401, 403, 404, 422),
)
async def get_doctor_verification_history(
    doctor_id: ObjectIdPath, admin: AdminUser, db: DB, settings: SettingsDep
) -> Any:
    require_platform_admin(admin)
    return await AdminService(db, settings).get_doctor_verification_history(doctor_id)


@router.patch(
    "/doctor-verification/{doctor_id}",
    response_model=DoctorOut,
    summary="Verify, suspend, or set pending status on a doctor profile",
    description="Updates `profile_status`, notifies the doctor, and logs the decision and reason to `audit_logs`. **Auth:** platform ADMIN.",
    responses=errs(401, 403, 404, 422),
)
async def patch_doctor_verification(
    doctor_id: ObjectIdPath,
    payload: DoctorProfileStatusUpdate,
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
) -> Any:
    require_platform_admin(admin)
    return to_api(
        await DoctorService(db, settings).set_profile_status(
            doctor_id, payload.profile_status, reason=payload.reason, actor=admin
        )
    )


@router.put(
    "/doctors/{doctor_id}/profile-status",
    response_model=DoctorOut,
    summary="Verify / suspend a doctor profile",
    description="`ACTIVE` lets the doctor publish availability and receive requests. **Auth:** platform ADMIN.",
    responses=errs(401, 403, 404, 422),
)
async def set_profile_status(
    doctor_id: ObjectIdPath,
    payload: DoctorProfileStatusUpdate,
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
) -> Any:
    require_platform_admin(admin)
    return to_api(
        await DoctorService(db, settings).set_profile_status(
            doctor_id, payload.profile_status, reason=payload.reason, actor=admin
        )
    )


@router.put(
    "/doctors/{doctor_id}/affiliations",
    response_model=DoctorOut,
    summary="Set a doctor's hospitals and departments",
    description="Replaces the doctor's affiliations; every department must belong to a listed hospital. **Auth:** platform ADMIN.",
    responses=errs(400, 401, 403, 404, 422),
)
async def set_affiliations(
    doctor_id: ObjectIdPath,
    payload: DoctorAffiliationUpdate,
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
) -> Any:
    require_platform_admin(admin)
    return to_api(await DoctorService(db, settings).set_affiliations(doctor_id, payload, actor=admin))


@router.get(
    "/routing-rules",
    response_model=Page[RoutingRuleOut],
    summary="List department-routing rules",
    description="Rules used by `/smart/department-suggestion`. **Auth:** platform ADMIN.",
    responses=errs(401, 403),
)
async def list_rules(admin: AdminUser, db: DB, params: Annotated[PageParams, Depends(page_params)]) -> Any:
    require_platform_admin(admin)
    items, total = await DepartmentRoutingService(db).list_rules(params)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.post(
    "/routing-rules",
    response_model=RoutingRuleOut,
    status_code=201,
    summary="Create a routing rule",
    description="Maps symptom keywords to a department name for routing only. **Auth:** platform ADMIN.",
    responses=errs(401, 403, 422),
)
async def create_rule(
    payload: RoutingRuleCreate, admin: AdminUser, db: DB, settings: SettingsDep
) -> Any:
    require_platform_admin(admin)
    doc = await DepartmentRoutingService(db).create_rule(payload)
    await AuditService(db, settings).log_event(
        action=AuditAction.ROUTING_RULE_CREATED,
        entity_type=AuditEntityType.ROUTING_RULE,
        entity_id=doc["_id"],
        actor_id=admin["_id"],
        actor_role=str(admin["role"]),
        description=f"Created symptom routing rule for department {doc['department_name']}",
        metadata={"department_name": doc["department_name"], "keyword_count": len(doc.get("keywords") or [])},
    )
    return to_api(doc)


@router.patch(
    "/routing-rules/{rule_id}",
    response_model=RoutingRuleOut,
    summary="Update a routing rule",
    description="**Auth:** platform ADMIN.",
    responses=errs(401, 403, 404, 422),
)
async def update_rule(
    rule_id: ObjectIdPath,
    payload: RoutingRuleUpdate,
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
) -> Any:
    require_platform_admin(admin)
    doc = await DepartmentRoutingService(db).update_rule(rule_id, payload)
    await AuditService(db, settings).log_event(
        action=AuditAction.ROUTING_RULE_UPDATED,
        entity_type=AuditEntityType.ROUTING_RULE,
        entity_id=doc["_id"],
        actor_id=admin["_id"],
        actor_role=str(admin["role"]),
        description=f"Updated symptom routing rule for department {doc['department_name']}",
        metadata={"department_name": doc["department_name"], "is_active": doc.get("is_active")},
    )
    return to_api(doc)


@router.delete(
    "/routing-rules/{rule_id}",
    status_code=204,
    summary="Delete a routing rule",
    description="**Auth:** platform ADMIN.",
    responses=errs(401, 403, 404, 422),
)
async def delete_rule(
    rule_id: ObjectIdPath, admin: AdminUser, db: DB, settings: SettingsDep
) -> None:
    require_platform_admin(admin)
    await DepartmentRoutingService(db).delete_rule(rule_id)
    await AuditService(db, settings).log_event(
        action=AuditAction.ROUTING_RULE_DELETED,
        entity_type=AuditEntityType.ROUTING_RULE,
        entity_id=str(rule_id),
        actor_id=admin["_id"],
        actor_role=str(admin["role"]),
        severity=AuditSeverity.WARNING,
        description=f"Deleted symptom routing rule {rule_id}",
    )


@router.get(
    "/statistics",
    response_model=AdminStatistics,
    summary="Platform-wide basic statistics",
    description=(
        "Total users/patients/doctors/hospitals/departments and appointment counts by status — "
        "all computed live from the database. **Auth:** platform ADMIN."
    ),
    responses=errs(401, 403),
)
async def get_statistics(admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    return await AdminService(db, settings).get_statistics()


@router.get(
    "/appointments",
    response_model=Page[AdminAppointmentOut],
    summary="Monitor appointments (read-only)",
    description=(
        "Platform-wide appointment visibility for monitoring, filterable by status, doctor, patient, hospital, "
        "department and date. A hospital-scoped admin only sees appointments at their own hospital(s). "
        "Excludes the patient's free-text reason and any other clinical detail. "
        "**Admins can never approve, reject, complete or mark an appointment no-show — the doctor is the sole decision-maker.**"
        " **Auth:** ADMIN (platform-wide or hospital-scoped)."
    ),
    responses=errs(401, 403, 422),
)
async def list_appointments_admin(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[AdminAppointmentSearchParams, Query()],
) -> Any:
    items, total = await AppointmentService(db, settings).list_for_admin(
        admin,
        params,
        status=q.status.value if q.status else None,
        doctor_id=q.doctor_id,
        patient_id=q.patient_id,
        hospital_id=q.hospital_id,
        department_id=q.department_id,
        appointment_date=q.appointment_date,
        date_from=q.date_from,
        date_to=q.date_to,
    )
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.post(
    "/maintenance/run",
    response_model=MaintenanceResult,
    summary="Run housekeeping now",
    description="Expires stale REQUESTED holds (freeing slots and notifying the waitlist), sends due reminders, and expires old waitlist entries. **Auth:** platform ADMIN.",
    responses=errs(401, 403),
)
async def run_maintenance(admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    result = await MaintenanceService(db, settings).run_all()
    await AuditService(db, settings).log_event(
        action=AuditAction.MAINTENANCE_RUN,
        entity_type=AuditEntityType.SYSTEM,
        actor_id=admin["_id"],
        actor_role=str(admin["role"]),
        description="Executed manual housekeeping maintenance run",
        metadata=result,
    )
    return result


@router.get(
    "/waitlist/statistics",
    response_model=AdminWaitlistStats,
    summary="Platform or hospital waitlist analytics",
    description="Active waitlist volume, pending slot offers, fulfilled entries, and hospital/department breakdowns. **Auth:** ADMIN.",
    responses=errs(401, 403),
)
async def get_admin_waitlist_statistics(admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    return await WaitlistService(db, settings).get_admin_waitlist_stats(admin.get("managed_hospital_ids"))


@router.get(
    "/waitlist",
    response_model=Page[WaitlistOut],
    summary="Monitor waitlist entries",
    description="View active, fulfilled, or cancelled waitlist entries across hospitals and departments. **Auth:** ADMIN.",
    responses=errs(400, 401, 403, 422),
)
async def list_admin_waitlist(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    hospital_id: str | None = None,
    department_id: str | None = None,
    doctor_id: str | None = None,
    status: WaitlistStatus | None = None,
) -> Any:
    items, total = await WaitlistService(db, settings).list_for_admin(
        params,
        hospital_id=hospital_id,
        department_id=department_id,
        doctor_id=doctor_id,
        status=status,
        hospital_scope=admin.get("managed_hospital_ids"),
    )
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)
