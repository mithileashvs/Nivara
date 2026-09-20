from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DB, CurrentUser, DoctorCtx, SettingsDep
from app.core.errors import ForbiddenError
from app.models.enums import UserRole
from app.routes.docs import errs
from app.schemas.common import Page, make_page
from app.schemas.scheduling import AvailabilityCreate, AvailabilityCreateResponse, AvailabilityOut
from app.schemas.users import DoctorIntakeUpdate, DoctorOut, DoctorPublicOut, DoctorSearchParams, DoctorStatistics, DoctorUpdate
from app.services.availability_service import AvailabilityService
from app.services.doctor_service import DoctorService, doctor_view
from app.services.hospital_service import can_manage_hospital
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api
from app.utils.time_utils import date_to_str
from datetime import date

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=Page[DoctorPublicOut], summary="Search doctors",
            description=("Find verified doctors by name, specialty, department, hospital, consultation type, city or distance. "
                         "`available=true` restricts to doctors with at least one genuinely bookable slot in the date range. **Auth:** any role."),
            responses=errs(400, 401, 422))
async def search_doctors(_u: CurrentUser, db: DB, settings: SettingsDep, filters: Annotated[DoctorSearchParams, Query()],
                         params: Annotated[PageParams, Depends(page_params)]) -> Any:
    items, total = await DoctorService(db, settings).search(filters, params)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("/me", response_model=DoctorOut, summary="Get my doctor profile", description="**Auth:** DOCTOR.", responses=errs(401, 403))
async def get_me(ctx: DoctorCtx) -> Any:
    return to_api(doctor_view(ctx.doctor))


@router.patch("/me", response_model=DoctorOut, summary="Update my doctor profile",
              description="Doctors edit experience, fee and consultation types. Specialty and hospital/department affiliations are verified by an admin. **Auth:** DOCTOR.",
              responses=errs(401, 403, 422))
async def update_me(payload: DoctorUpdate, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await DoctorService(db, settings).update_me(ctx.doctor, payload))


@router.get("/me/statistics", response_model=DoctorStatistics, summary="My basic statistics",
            description=("Today's appointments, pending requests, confirmed/completed counts and total distinct patients — "
                         "all computed live from actual appointment records. **Auth:** DOCTOR."),
            responses=errs(401, 403))
async def get_my_statistics(ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return await DoctorService(db, settings).get_statistics(ctx.doctor)


@router.post("/me/availability", response_model=AvailabilityCreateResponse, status_code=201, summary="Add a working window or time off",
             description=("`status=WORKING` generates appointment slots (idempotent). `status=BLOCKED` blocks overlapping FREE slots — slots that already "
                          "have pending/confirmed appointments are left untouched. Requires an ACTIVE, affiliated profile. **Auth:** DOCTOR (own schedule only)."),
             responses=errs(400, 401, 403, 404, 409, 422))
async def add_availability(payload: AvailabilityCreate, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await AvailabilityService(db, settings).create(ctx.doctor, payload))


@router.get("/me/availability", response_model=Page[AvailabilityOut], summary="List my availability windows",
            description="**Auth:** DOCTOR.", responses=errs(401, 403))
async def list_availability(ctx: DoctorCtx, db: DB, settings: SettingsDep, params: Annotated[PageParams, Depends(page_params)],
                            date_from: date | None = None, date_to: date | None = None) -> Any:
    items, total = await AvailabilityService(db, settings).list_for_doctor(
        ctx.doctor["_id"], params, date_to_str(date_from) if date_from else None, date_to_str(date_to) if date_to else None)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.delete("/me/availability/{availability_id}", summary="Delete an availability window",
               description="Removing a WORKING window deletes its unreserved slots (409 if any have pending/confirmed appointments). Removing a BLOCKED window unblocks its slots. **Auth:** DOCTOR.",
               responses=errs(401, 403, 404, 409))
async def delete_availability(availability_id: ObjectIdPath, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> dict:
    return await AvailabilityService(db, settings).delete(ctx.doctor["_id"], availability_id)


@router.put("/{doctor_id}/intake-status", response_model=DoctorPublicOut, summary="Open/close a doctor's new-appointment intake",
            description=("Closing stops NEW requests to the doctor; existing appointments are untouched. Allowed for the doctor themself, or an admin "
                         "authorised for one of the doctor's hospitals. **Auth:** DOCTOR (self) or ADMIN."),
            responses=errs(401, 403, 404, 422))
async def set_intake(doctor_id: ObjectIdPath, payload: DoctorIntakeUpdate, user: CurrentUser, db: DB, settings: SettingsDep) -> Any:
    svc = DoctorService(db, settings)
    doctor = await svc.get_any(doctor_id)
    is_self = user["role"] == UserRole.DOCTOR and doctor["user_id"] == user["_id"]
    is_admin = user["role"] == UserRole.ADMIN and (
        user.get("managed_hospital_ids") is None or any(can_manage_hospital(user, h) for h in doctor.get("hospital_ids", []))
    )
    if not (is_self or is_admin):
        raise ForbiddenError("You cannot change this doctor's intake status", code="forbidden_role")
    updated, _ = await svc.set_intake(doctor_id, payload.availability_status)
    return to_api(updated)


@router.get("/{doctor_id}", response_model=DoctorPublicOut, summary="Get a doctor's public profile",
            description="**Auth:** any role.", responses=errs(401, 404, 422))
async def get_doctor(doctor_id: ObjectIdPath, _u: CurrentUser, db: DB, settings: SettingsDep) -> Any:
    return to_api(await DoctorService(db, settings).get_public(doctor_id))
