import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, WebSocket, WebSocketDisconnect, status

from app.core.dependencies import DB, CurrentUser
from app.core.security import decode_access_token
from app.database.collections import C
from app.routes.docs import errs
from app.schemas.common import MessageResponse, Page, make_page
from app.schemas.engagement import (
    NotificationOut,
    NotificationPreferencesOut,
    NotificationPreferencesUpdate,
    UnreadCountOut,
)
from app.services.connection_manager import notification_manager
from app.services.notification_service import NotificationService
from app.utils.object_id import ObjectIdPath, oid
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

logger = logging.getLogger("nivara.notifications")

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.websocket("/ws")
async def notifications_websocket(
    websocket: WebSocket,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """Authenticated WebSocket endpoint for real-time notification delivery.
    Clients connect with `?token=<jwt_access_token>`.
    On connection, registers the user channel and sends current unread count.
    Delivery is supplementary; PostgreSQL remains the persistent source of truth.
    """
    db = websocket.app.state.db
    settings = websocket.app.state.settings

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        claims = decode_access_token(token, settings)
        user_id = oid(claims["sub"])
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = await db[C.USERS].find_one({"_id": user_id, "is_active": True})
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await notification_manager.connect(user["_id"], websocket)
    try:
        # Send initial ACK with current unread count
        unread = await NotificationService(db).unread_count(user["_id"])
        await websocket.send_json(
            {"event": "connected", "user_id": str(user["_id"]), "unread": unread}
        )

        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await notification_manager.disconnect(user["_id"], websocket)
    except Exception:
        await notification_manager.disconnect(user["_id"], websocket)


@router.get(
    "",
    response_model=Page[NotificationOut],
    summary="List my notifications",
    description="Newest first; filter by `is_read` and `category`. **Auth:** any role.",
    responses=errs(401, 422),
)
async def list_notifications(
    user: CurrentUser,
    db: DB,
    params: Annotated[PageParams, Depends(page_params)],
    is_read: bool | None = None,
    category: str | None = None,
) -> Any:
    items, total = await NotificationService(db).list_for_user(
        user["_id"], params, is_read=is_read, category=category
    )
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get(
    "/unread-count",
    response_model=UnreadCountOut,
    summary="Count unread notifications",
    description="**Auth:** any role.",
    responses=errs(401),
)
async def unread_count(
    user: CurrentUser, db: DB, category: str | None = None
) -> Any:
    return {"unread": await NotificationService(db).unread_count(user["_id"], category=category)}


@router.get(
    "/preferences",
    response_model=NotificationPreferencesOut,
    summary="Get my notification preferences",
    description="Returns enabled status for notification categories. **Auth:** any role.",
    responses=errs(401),
)
async def get_preferences(user: CurrentUser, db: DB) -> Any:
    return await NotificationService(db).get_preferences(user["_id"])


@router.put(
    "/preferences",
    response_model=NotificationPreferencesOut,
    summary="Update my notification preferences",
    description="Toggle notification delivery for optional categories. **Auth:** any role.",
    responses=errs(401, 422),
)
async def update_preferences(
    payload: NotificationPreferencesUpdate, user: CurrentUser, db: DB
) -> Any:
    return await NotificationService(db).update_preferences(user["_id"], payload)


@router.patch(
    "/read-all",
    response_model=MessageResponse,
    summary="Mark all my notifications read",
    description="**Auth:** any role.",
    responses=errs(401),
)
@router.post(
    "/read-all",
    response_model=MessageResponse,
    summary="Mark all my notifications read (POST alias)",
    description="**Auth:** any role.",
    responses=errs(401),
)
async def read_all(
    user: CurrentUser, db: DB, category: str | None = None
) -> Any:
    n = await NotificationService(db).mark_all_read(user["_id"], category=category)
    return {"message": f"{n} notification(s) marked as read"}


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark a notification read",
    description="Only your own notifications; otherwise 404. **Auth:** any role.",
    responses=errs(401, 404, 422),
)
@router.post(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark a notification read (POST alias)",
    description="Only your own notifications; otherwise 404. **Auth:** any role.",
    responses=errs(401, 404, 422),
)
async def mark_read(notification_id: ObjectIdPath, user: CurrentUser, db: DB) -> Any:
    return to_api(await NotificationService(db).mark_read(user["_id"], notification_id))


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete / dismiss a notification",
    description="Only your own notifications; otherwise 404. **Auth:** any role.",
    responses=errs(401, 404, 422),
)
async def delete_notification(
    notification_id: ObjectIdPath, user: CurrentUser, db: DB
) -> Response:
    await NotificationService(db).delete_notification(user["_id"], notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
