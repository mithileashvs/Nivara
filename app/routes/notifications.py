from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, CurrentUser
from app.routes.docs import errs
from app.schemas.common import MessageResponse, Page, make_page
from app.schemas.engagement import NotificationOut, UnreadCountOut
from app.services.notification_service import NotificationService
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=Page[NotificationOut], summary="List my notifications",
            description="Newest first; filter with `is_read`. **Auth:** any role.", responses=errs(401, 422))
async def list_notifications(user: CurrentUser, db: DB, params: Annotated[PageParams, Depends(page_params)], is_read: bool | None = None) -> Any:
    items, total = await NotificationService(db).list_for_user(user["_id"], params, is_read)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("/unread-count", response_model=UnreadCountOut, summary="Count unread notifications",
            description="**Auth:** any role.", responses=errs(401))
async def unread_count(user: CurrentUser, db: DB) -> Any:
    return {"unread": await NotificationService(db).unread_count(user["_id"])}


@router.post("/read-all", response_model=MessageResponse, summary="Mark all my notifications read",
             description="**Auth:** any role.", responses=errs(401))
async def read_all(user: CurrentUser, db: DB) -> Any:
    n = await NotificationService(db).mark_all_read(user["_id"])
    return {"message": f"{n} notification(s) marked as read"}


@router.post("/{notification_id}/read", response_model=NotificationOut, summary="Mark a notification read",
             description="Only your own notifications; otherwise 404. **Auth:** any role.", responses=errs(401, 404, 422))
async def mark_read(notification_id: ObjectIdPath, user: CurrentUser, db: DB) -> Any:
    return to_api(await NotificationService(db).mark_read(user["_id"], notification_id))
