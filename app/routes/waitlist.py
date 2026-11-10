from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, PatientCtx, SettingsDep
from app.models.enums import WaitlistOfferStatus, WaitlistStatus
from app.routes.docs import errs
from app.schemas.common import Page, make_page
from app.schemas.engagement import (
    WaitlistCreate,
    WaitlistOfferDecision,
    WaitlistOfferOut,
    WaitlistOut,
)
from app.services.waitlist_service import WaitlistService
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/waitlist", tags=["Smart Waitlist"])


@router.post(
    "",
    response_model=WaitlistOut,
    status_code=201,
    summary="Join the smart waitlist",
    description=(
        "Ask to be notified and receive time-limited slot offers when a matching appointment opens. "
        "A compatible freed slot automatically creates a reserved slot offer for you to accept. "
        "**Auth:** PATIENT."
    ),
    responses=errs(400, 401, 403, 404, 409, 422),
)
async def join_waitlist(
    payload: WaitlistCreate, ctx: PatientCtx, db: DB, settings: SettingsDep
) -> Any:
    return to_api(await WaitlistService(db, settings).create(ctx.patient, payload))


@router.get(
    "",
    response_model=Page[WaitlistOut],
    summary="List my waitlist entries",
    description="Returns active and past waitlist entries with dynamic queue position. **Auth:** PATIENT.",
    responses=errs(401, 403, 422),
)
async def list_waitlist(
    ctx: PatientCtx,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    status: WaitlistStatus | None = None,
) -> Any:
    items, total = await WaitlistService(db, settings).list_mine(
        ctx.patient["_id"], params, status
    )
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get(
    "/offers",
    response_model=list[WaitlistOfferOut],
    summary="List my slot offers",
    description="View time-limited appointment slot offers reserved for you. **Auth:** PATIENT.",
    responses=errs(401, 403),
)
async def list_offers(
    ctx: PatientCtx,
    db: DB,
    settings: SettingsDep,
    status: WaitlistOfferStatus | None = None,
) -> Any:
    offers = await WaitlistService(db, settings).list_offers_for_patient(
        ctx.patient["_id"], status
    )
    return [to_api(o) for o in offers]


@router.get(
    "/history",
    response_model=Page[WaitlistOut],
    summary="View waitlist history",
    description="View fulfilled, cancelled, or expired waitlist entries. **Auth:** PATIENT.",
    responses=errs(401, 403, 422),
)
async def waitlist_history(
    ctx: PatientCtx,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
) -> Any:
    items, total = await WaitlistService(db, settings).list_mine(
        ctx.patient["_id"], params, None, exclude_active=True
    )
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.post(
    "/offers/{offer_id}/accept",
    summary="Accept a waitlist slot offer",
    description=(
        "Converts the held slot offer into a formal appointment request (REQUESTED status), "
        "preserving doctor approval. Fulfills the waitlist entry and records history. **Auth:** PATIENT."
    ),
    responses=errs(401, 403, 404, 409, 422),
)
async def accept_offer(
    offer_id: ObjectIdPath,
    payload: WaitlistOfferDecision,
    ctx: PatientCtx,
    db: DB,
    settings: SettingsDep,
) -> Any:
    result = await WaitlistService(db, settings).accept_offer(
        ctx.patient, offer_id, payload.reason
    )
    return {
        "offer": to_api(result["offer"]),
        "appointment": to_api(result["appointment"]),
    }


@router.post(
    "/offers/{offer_id}/decline",
    response_model=WaitlistOfferOut,
    summary="Decline a waitlist slot offer",
    description=(
        "Declines the slot offer, releases the held slot, and triggers automatic queue progression "
        "for the next eligible waitlisted patient. **Auth:** PATIENT."
    ),
    responses=errs(401, 403, 404, 409, 422),
)
async def decline_offer(
    offer_id: ObjectIdPath,
    payload: WaitlistOfferDecision,
    ctx: PatientCtx,
    db: DB,
    settings: SettingsDep,
) -> Any:
    declined = await WaitlistService(db, settings).decline_offer(
        ctx.patient, offer_id, payload.reason
    )
    return to_api(declined)


@router.get(
    "/{entry_id}",
    response_model=WaitlistOut,
    summary="Get a waitlist entry",
    description="**Auth:** PATIENT (own entries only; others 404).",
    responses=errs(401, 403, 404, 422),
)
async def get_entry(
    entry_id: ObjectIdPath, ctx: PatientCtx, db: DB, settings: SettingsDep
) -> Any:
    return to_api(await WaitlistService(db, settings).get_mine(ctx.patient["_id"], entry_id))


@router.delete(
    "/{entry_id}",
    response_model=WaitlistOut,
    summary="Leave the waitlist",
    description="Cancels an ACTIVE entry and releases any pending held offer. **Auth:** PATIENT.",
    responses=errs(401, 403, 404, 409, 422),
)
async def cancel_entry(
    entry_id: ObjectIdPath, ctx: PatientCtx, db: DB, settings: SettingsDep
) -> Any:
    return to_api(await WaitlistService(db, settings).cancel(ctx.patient["_id"], entry_id))
