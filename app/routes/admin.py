from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DB, AdminUser, SettingsDep
from app.models.enums import ProfileStatus, UserRole
from app.routes.docs import errs
from app.schemas.admin import (
    AdminScopeUpdate, AdminStatistics, AdminUserCreate, MaintenanceResult, RoutingRuleCreate, RoutingRuleOut, RoutingRuleUpdate,
    UserActiveUpdate,
)
from app.schemas.appointments import AdminAppointmentOut, AdminAppointmentSearchParams
from app.schemas.auth import UserOut
from app.schemas.common import Page, make_page
from app.schemas.users import DoctorAffiliationUpdate, DoctorOut, DoctorProfileStatusUpdate
from app.services.admin_service import AdminService, require_platform_admin
from app.services.appointment_service import AppointmentService
from app.services.department_routing_service import DepartmentRoutingService
from app.services.doctor_service import DoctorService, doctor_view
from app.services.maintenance_service import MaintenanceService
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params, paginate
from app.utils.serialization import to_api
from app.database.collections import C

router = APIRouter(prefix="/admin", tags=["Admin"])
NOTE = " Admins manage platform resources only — they never approve individual appointments."


@router.post("/users", response_model=UserOut, status_code=201, summary="Create an admin user",
             description="Omit `managed_hospital_ids` for a platform admin; pass a list for a hospital administrator scoped to those hospitals. **Auth:** platform ADMIN." + NOTE,
             responses=errs(400, 401, 403, 409, 422))
async def create_admin(payload: AdminUserCreate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    return to_api(await AdminService(db, settings).create_admin(payload))


@router.get("/users", response_model=Page[UserOut], summary="List users",
            description="Filter by role / active flag. **Auth:** platform ADMIN.", responses=errs(401, 403, 422))
async def list_users(admin: AdminUser, db: DB, settings: SettingsDep, params: Annotated[PageParams, Depends(page_params)],
                     role: UserRole | None = None, is_active: bool | None = None) -> Any:
    require_platform_admin(admin)
    items, total = await AdminService(db, settings).list_users(params, role, is_active)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.put("/users/{user_id}/active", response_model=UserOut, summary="Activate or deactivate a user",
            description="Deactivated users lose access immediately. You cannot change your own status. **Auth:** platform ADMIN.", responses=errs(400, 401, 403, 404, 422))
async def set_active(user_id: ObjectIdPath, payload: UserActiveUpdate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    return to_api(await AdminService(db, settings).set_active(admin, user_id, payload.is_active))


@router.put("/users/{user_id}/hospital-scope", response_model=UserOut, summary="Set an admin's hospital scope",
            description="`null` = platform-wide; list = hospital administrator. **Auth:** platform ADMIN.", responses=errs(400, 401, 403, 404, 422))
async def set_scope(user_id: ObjectIdPath, payload: AdminScopeUpdate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    return to_api(await AdminService(db, settings).set_scope(user_id, payload.managed_hospital_ids))


@router.get("/doctors", response_model=Page[DoctorOut], summary="List doctor profiles (any status)",
            description="Use `profile_status=PENDING` to find doctors awaiting verification. **Auth:** platform ADMIN.", responses=errs(401, 403, 422))
async def list_doctors(admin: AdminUser, db: DB, params: Annotated[PageParams, Depends(page_params)], profile_status: ProfileStatus | None = None) -> Any:
    require_platform_admin(admin)
    q = {"profile_status": profile_status.value} if profile_status else {}
    items, total = await paginate(db[C.DOCTORS], q, params, sort=[("created_at", -1)])
    return make_page([to_api(doctor_view(i)) for i in items], total, params.page, params.page_size)


@router.put("/doctors/{doctor_id}/profile-status", response_model=DoctorOut, summary="Verify / suspend a doctor profile",
            description="`ACTIVE` lets the doctor publish availability and receive requests. **Auth:** platform ADMIN.", responses=errs(401, 403, 404, 422))
async def set_profile_status(doctor_id: ObjectIdPath, payload: DoctorProfileStatusUpdate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    return to_api(await DoctorService(db, settings).set_profile_status(doctor_id, payload.profile_status))


@router.put("/doctors/{doctor_id}/affiliations", response_model=DoctorOut, summary="Set a doctor's hospitals and departments",
            description="Replaces the doctor's affiliations; every department must belong to a listed hospital. **Auth:** platform ADMIN.", responses=errs(400, 401, 403, 404, 422))
async def set_affiliations(doctor_id: ObjectIdPath, payload: DoctorAffiliationUpdate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    return to_api(await DoctorService(db, settings).set_affiliations(doctor_id, payload))


@router.get("/routing-rules", response_model=Page[RoutingRuleOut], summary="List department-routing rules",
            description="Rules used by `/smart/department-suggestion`. **Auth:** platform ADMIN.", responses=errs(401, 403))
async def list_rules(admin: AdminUser, db: DB, params: Annotated[PageParams, Depends(page_params)]) -> Any:
    require_platform_admin(admin)
    items, total = await DepartmentRoutingService(db).list_rules(params)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.post("/routing-rules", response_model=RoutingRuleOut, status_code=201, summary="Create a routing rule",
             description="Maps symptom keywords to a department name for routing only. **Auth:** platform ADMIN.", responses=errs(401, 403, 422))
async def create_rule(payload: RoutingRuleCreate, admin: AdminUser, db: DB) -> Any:
    require_platform_admin(admin)
    return to_api(await DepartmentRoutingService(db).create_rule(payload))


@router.patch("/routing-rules/{rule_id}", response_model=RoutingRuleOut, summary="Update a routing rule",
              description="**Auth:** platform ADMIN.", responses=errs(401, 403, 404, 422))
async def update_rule(rule_id: ObjectIdPath, payload: RoutingRuleUpdate, admin: AdminUser, db: DB) -> Any:
    require_platform_admin(admin)
    return to_api(await DepartmentRoutingService(db).update_rule(rule_id, payload))


@router.delete("/routing-rules/{rule_id}", status_code=204, summary="Delete a routing rule",
               description="**Auth:** platform ADMIN.", responses=errs(401, 403, 404, 422))
async def delete_rule(rule_id: ObjectIdPath, admin: AdminUser, db: DB) -> None:
    require_platform_admin(admin)
    await DepartmentRoutingService(db).delete_rule(rule_id)


@router.get("/statistics", response_model=AdminStatistics, summary="Platform-wide basic statistics",
            description=("Total users/patients/doctors/hospitals/departments and appointment counts by status — "
                         "all computed live from the database. **Auth:** platform ADMIN."),
            responses=errs(401, 403))
async def get_statistics(admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    return await AdminService(db, settings).get_statistics()


@router.get("/appointments", response_model=Page[AdminAppointmentOut], summary="Monitor appointments (read-only)",
            description=("Platform-wide appointment visibility for monitoring, filterable by status, doctor, patient, hospital, "
                         "department and date. A hospital-scoped admin only sees appointments at their own hospital(s). "
                         "Excludes the patient's free-text reason and any other clinical detail. "
                         "**Admins can never approve, reject, complete or mark an appointment no-show — the doctor is the sole decision-maker.**"
                         " **Auth:** ADMIN (platform-wide or hospital-scoped)."),
            responses=errs(401, 403, 422))
async def list_appointments_admin(admin: AdminUser, db: DB, settings: SettingsDep, params: Annotated[PageParams, Depends(page_params)],
                                  q: Annotated[AdminAppointmentSearchParams, Query()]) -> Any:
    items, total = await AppointmentService(db, settings).list_for_admin(
        admin, params, status=q.status.value if q.status else None, doctor_id=q.doctor_id, patient_id=q.patient_id,
        hospital_id=q.hospital_id, department_id=q.department_id, appointment_date=q.appointment_date,
        date_from=q.date_from, date_to=q.date_to,
    )
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.post("/maintenance/run", response_model=MaintenanceResult, summary="Run housekeeping now",
             description="Expires stale REQUESTED holds (freeing slots and notifying the waitlist), sends due reminders, and expires old waitlist entries. The same job runs periodically in the background. **Auth:** platform ADMIN.",
             responses=errs(401, 403))
async def run_maintenance(admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    require_platform_admin(admin)
    return await MaintenanceService(db, settings).run_all()
