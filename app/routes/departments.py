from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, AdminUser, CurrentUser, SettingsDep
from app.models.enums import DepartmentStatus
from app.routes.docs import errs
from app.schemas.common import Page, make_page
from app.schemas.facilities import DepartmentCreate, DepartmentOut, DepartmentUpdate, IntakeUpdateRequest, IntakeUpdateResponse
from app.services.hospital_service import HospitalService
from app.utils.object_id import ObjectIdPath, ObjectIdStr
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.post("", response_model=DepartmentOut, status_code=201, summary="Create a department",
             description="**Auth:** ADMIN authorised for the hospital.", responses=errs(401, 403, 404, 409, 422))
async def create_department(payload: DepartmentCreate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    return to_api(await HospitalService(db, settings).create_department(admin, payload))


@router.get("", response_model=Page[DepartmentOut], summary="List departments",
            description="**Auth:** any role.", responses=errs(401, 422))
async def list_departments(_u: CurrentUser, db: DB, settings: SettingsDep, params: Annotated[PageParams, Depends(page_params)],
                           hospital_id: ObjectIdStr | None = None, status: DepartmentStatus | None = None) -> Any:
    items, total = await HospitalService(db, settings).list_departments(params, hospital_id=hospital_id, status=status)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("/{department_id}", response_model=DepartmentOut, summary="Get a department",
            description="**Auth:** any role.", responses=errs(401, 404, 422))
async def get_department(department_id: ObjectIdPath, _u: CurrentUser, db: DB, settings: SettingsDep) -> Any:
    return to_api(await HospitalService(db, settings).get_department(department_id))


@router.patch("/{department_id}", response_model=DepartmentOut, summary="Update a department",
              description="**Auth:** ADMIN authorised for the hospital.", responses=errs(401, 403, 404, 409, 422))
async def update_department(department_id: ObjectIdPath, payload: DepartmentUpdate, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    return to_api(await HospitalService(db, settings).update_department(admin, department_id, payload))


@router.put("/{department_id}/intake", response_model=IntakeUpdateResponse, summary="Open or close department appointment intake",
            description=("Example: Cardiology `CLOSED` while General Medicine stays `OPEN`. New Cardiology requests are rejected; existing appointments "
                         "are untouched. **Auth:** ADMIN authorised for the hospital."),
            responses=errs(401, 403, 404, 422))
async def set_department_intake(department_id: ObjectIdPath, payload: IntakeUpdateRequest, admin: AdminUser, db: DB, settings: SettingsDep) -> Any:
    result = await HospitalService(db, settings).set_intake(admin, target_type="DEPARTMENT", target_id=department_id, status=payload.status, reason=payload.reason)
    return to_api(result)
