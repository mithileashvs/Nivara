from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, AdminUser, CurrentUser, SettingsDep
from app.models.enums import IntakeStatus
from app.routes.docs import errs
from app.schemas.common import Page, make_page
from app.schemas.facilities import (
    HospitalAvailabilityOut, HospitalCreate, HospitalDetailOut, HospitalOut, HospitalUpdate, IntakeUpdateRequest, IntakeUpdateResponse,
)
from app.services.hospital_service import HospitalService
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])


@router.post("", response_model=HospitalOut, status_code=201, summary="Create a hospital",
             description="**Auth:** platform-wide ADMIN (hospital-scoped admins cannot create hospitals).", responses=errs(401, 403, 422))
async def create_hospital(payload: HospitalCreate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    return to_api(await HospitalService(db, settings).create_hospital(admin, payload))


@router.get("", response_model=Page[HospitalOut], summary="List hospitals",
            description="Filter by city, name, or intake status. **Auth:** any role.", responses=errs(401, 422))
async def list_hospitals(_u: CurrentUser, db: DB, settings: SettingsDep, params: Annotated[PageParams, Depends(page_params)],
                         city: str | None = None, q: str | None = None, intake_status: IntakeStatus | None = None) -> Any:
    items, total = await HospitalService(db, settings).list_hospitals(params, city=city, q=q, intake=intake_status)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("/{hospital_id}", response_model=HospitalDetailOut, summary="Get a hospital with its departments",
            description="Includes each department's explicit intake status. **Auth:** any role.", responses=errs(401, 404, 422))
async def get_hospital(hospital_id: ObjectIdPath, _u: CurrentUser, db: DB, settings: SettingsDep) -> Any:
    return to_api(await HospitalService(db, settings).get_hospital_detail(hospital_id))


@router.patch("/{hospital_id}", response_model=HospitalOut, summary="Update a hospital",
              description="**Auth:** ADMIN authorised for this hospital.", responses=errs(401, 403, 404, 422))
async def update_hospital(hospital_id: ObjectIdPath, payload: HospitalUpdate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    return to_api(await HospitalService(db, settings).update_hospital(admin, hospital_id, payload))


@router.put("/{hospital_id}/intake", response_model=IntakeUpdateResponse, summary="Open or close hospital-wide appointment intake",
            description=("`CLOSED` rejects all NEW appointment requests for this hospital and hides its slots as non-bookable. Existing pending and "
                         "confirmed appointments are **not** cancelled — the response reports how many were left untouched. Every change is audited. "
                         "**Auth:** ADMIN authorised for this hospital."),
            responses=errs(401, 403, 404, 422))
async def set_hospital_intake(hospital_id: ObjectIdPath, payload: IntakeUpdateRequest, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    result = await HospitalService(db, settings).set_intake(admin, target_type="HOSPITAL", target_id=hospital_id, status=payload.status, reason=payload.reason)
    return to_api(result)


@router.get("/{hospital_id}/availability", response_model=HospitalAvailabilityOut, summary="Hospital appointment availability",
            description=("Availability from ACTUAL open slots plus explicit intake flags. Reports `No available appointment slots` when nothing is open; "
                         "it never estimates or infers hospital 'load'. **Auth:** any role."),
            responses=errs(400, 401, 404, 422))
async def hospital_availability(hospital_id: ObjectIdPath, _u: CurrentUser, db: DB, settings: SettingsDep,
                                date_from: date | None = None, date_to: date | None = None) -> Any:
    return to_api(await HospitalService(db, settings).availability_report(hospital_id, date_from, date_to))
