from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, AdminUser, CurrentUser, PatientCtx
from app.routes.docs import errs
from app.schemas.clinical import ReviewCreate, ReviewOwnOut, ReviewPublicOut
from app.schemas.common import Page, make_page
from app.services.review_service import ReviewService
from app.utils.object_id import ObjectIdPath, ObjectIdStr
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("", response_model=ReviewOwnOut, status_code=201, summary="Review a completed appointment",
             description="Only the patient of a `COMPLETED` appointment, once per appointment (duplicate → 409). **Auth:** PATIENT.",
             responses=errs(401, 403, 404, 409, 422))
async def create_review(payload: ReviewCreate, ctx: PatientCtx, db: DB) -> Any:
    return to_api(await ReviewService(db).create(ctx.patient["_id"], payload))


@router.get("/mine", response_model=Page[ReviewOwnOut], summary="List reviews I wrote",
            description="**Auth:** PATIENT.", responses=errs(401, 403))
async def my_reviews(ctx: PatientCtx, db: DB, params: Annotated[PageParams, Depends(page_params)]) -> Any:
    items, total = await ReviewService(db).list_mine(ctx.patient["_id"], params)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("", response_model=Page[ReviewPublicOut], summary="List a doctor's reviews",
            description="Patient identities are not exposed. **Auth:** any role.", responses=errs(401, 422))
async def doctor_reviews(doctor_id: ObjectIdStr, _u: CurrentUser, db: DB, params: Annotated[PageParams, Depends(page_params)]) -> Any:
    items, total = await ReviewService(db).list_for_doctor(doctor_id, params)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.delete("/{review_id}", status_code=204, summary="Remove a review (moderation)",
               description="**Auth:** ADMIN.", responses=errs(401, 403, 404, 422))
async def delete_review(review_id: ObjectIdPath, _admin: AdminUser, db: DB) -> None:
    await ReviewService(db).delete(review_id)
