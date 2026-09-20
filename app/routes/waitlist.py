from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, PatientCtx, SettingsDep
from app.models.enums import WaitlistStatus
from app.routes.docs import errs
from app.schemas.common import Page, make_page
from app.schemas.engagement import WaitlistCreate, WaitlistOut
from app.services.waitlist_service import WaitlistService
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/waitlist", tags=["Smart Waitlist"])


@router.post("", response_model=WaitlistOut, status_code=201, summary="Join the smart waitlist",
             description=("Ask to be notified when a matching appointment opens (e.g. an EARLIER dermatology slot). Set `existing_appointment_id` to only "
                          "match slots earlier than that appointment. When a slot is freed, eligible patients are notified with transparent match factors. "
                          "Nothing is booked automatically — you must request the slot and the doctor must confirm. **Auth:** PATIENT."),
             responses=errs(400, 401, 403, 404, 409, 422))
async def join_waitlist(payload: WaitlistCreate, ctx: PatientCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await WaitlistService(db, settings).create(ctx.patient, payload))


@router.get("", response_model=Page[WaitlistOut], summary="List my waitlist entries",
            description="**Auth:** PATIENT.", responses=errs(401, 403, 422))
async def list_waitlist(ctx: PatientCtx, db: DB, settings: SettingsDep, params: Annotated[PageParams, Depends(page_params)],
                        status: WaitlistStatus | None = None) -> Any:
    items, total = await WaitlistService(db, settings).list_mine(ctx.patient["_id"], params, status)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("/{entry_id}", response_model=WaitlistOut, summary="Get a waitlist entry",
            description="**Auth:** PATIENT (own entries only; others 404).", responses=errs(401, 403, 404, 422))
async def get_entry(entry_id: ObjectIdPath, ctx: PatientCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await WaitlistService(db, settings).get_mine(ctx.patient["_id"], entry_id))


@router.delete("/{entry_id}", response_model=WaitlistOut, summary="Leave the waitlist",
               description="Cancels an ACTIVE entry. **Auth:** PATIENT.", responses=errs(401, 403, 404, 409, 422))
async def cancel_entry(entry_id: ObjectIdPath, ctx: PatientCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await WaitlistService(db, settings).cancel(ctx.patient["_id"], entry_id))
