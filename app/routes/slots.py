from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DB, CurrentUser, DoctorCtx, SettingsDep
from app.routes.docs import errs
from app.schemas.common import Page, make_page
from app.schemas.scheduling import SlotDoctorOut, SlotDoctorSearchParams, SlotPublicOut, SlotSearchParams
from app.services.slot_service import SlotService
from app.utils.object_id import ObjectIdPath, oid
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/slots", tags=["Slots"])


@router.get("", response_model=Page[SlotPublicOut], summary="View a doctor's availability",
            description=("Bookable slots for a doctor (default: next 14 days, max 31). Every slot carries a backend-computed `bookable` flag — "
                         "the frontend must never decide availability itself. With `include_unavailable=true` HELD/BOOKED/BLOCKED slots are included "
                         "with their status and reason so a full day schedule can be drawn. **Auth:** any role."),
            responses=errs(400, 401, 404, 422))
async def search_slots(_u: CurrentUser, db: DB, settings: SettingsDep, q: Annotated[SlotSearchParams, Query()],
                       params: Annotated[PageParams, Depends(page_params)]) -> Any:
    items, total = await SlotService(db, settings).search_for_patients(
        doctor_id=q.doctor_id, date_from=q.date_from, date_to=q.date_to, hospital_id=q.hospital_id, department_id=q.department_id,
        include_unavailable=q.include_unavailable, params=params)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("/me", response_model=Page[SlotDoctorOut], summary="My full schedule (all slot states)",
            description="**Auth:** DOCTOR (own slots only).", responses=errs(400, 401, 403, 422))
async def my_slots(ctx: DoctorCtx, db: DB, settings: SettingsDep, q: Annotated[SlotDoctorSearchParams, Query()],
                   params: Annotated[PageParams, Depends(page_params)]) -> Any:
    items, total = await SlotService(db, settings).list_for_doctor(ctx.doctor, date_from=q.date_from, date_to=q.date_to, status=q.status, params=params)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.post("/{slot_id}/block", response_model=SlotDoctorOut, summary="Manually block a free slot",
             description="Only an AVAILABLE slot of your own can be blocked. **Auth:** DOCTOR.", responses=errs(401, 403, 404, 409, 422))
async def block_slot(slot_id: ObjectIdPath, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    svc = SlotService(db, settings)
    slot = await svc.block_slot(ctx.doctor["_id"], oid(slot_id))
    return to_api((await svc._present([slot], {ctx.doctor["_id"]: ctx.doctor}, slot["updated_at"], detailed=True))[0])


@router.post("/{slot_id}/unblock", response_model=SlotDoctorOut, summary="Unblock a manually blocked slot",
             description="Only slots you blocked manually (not time-off windows). **Auth:** DOCTOR.", responses=errs(401, 403, 404, 409, 422))
async def unblock_slot(slot_id: ObjectIdPath, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    svc = SlotService(db, settings)
    slot = await svc.unblock_slot(ctx.doctor["_id"], oid(slot_id))
    return to_api((await svc._present([slot], {ctx.doctor["_id"]: ctx.doctor}, slot["updated_at"], detailed=True))[0])
