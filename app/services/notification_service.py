import logging
from typing import Any

from app.core.errors import NotFoundError
from app.database.collections import C
from app.models.engagement import Notification
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate
from app.utils.time_utils import utcnow

logger = logging.getLogger("nivara.notifications")


class NotificationService:
    """In-app notifications. Delivery channels (email/SMS/push) can be added behind `notify`."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def notify(
        self,
        *,
        user_id: Any,
        type: str,
        title: str,
        message: str,
        appointment_id: Any = None,
        data: dict | None = None,
    ) -> dict | None:
        """Create a notification. Never raises — a notification failure must not break a booking flow."""
        try:
            doc = Notification(
                user_id=str(user_id),
                type=type,
                title=title,
                message=message,
                related_appointment_id=str(appointment_id) if appointment_id else None,
                data=data or {},
            ).to_mongo()
            await self.db[C.NOTIFICATIONS].insert_one(doc)
            return doc
        except Exception:  # noqa: BLE001
            logger.exception("Failed to create notification type=%s user=%s", type, user_id)
            return None

    async def list_for_user(
        self, user_id: Any, params: PageParams, is_read: bool | None = None
    ) -> tuple[list[dict], int]:
        query: dict[str, Any] = {"user_id": str(user_id)}
        if is_read is not None:
            query["is_read"] = is_read
        return await paginate(self.db[C.NOTIFICATIONS], query, params, sort=[("created_at", -1), ("_id", -1)])

    async def unread_count(self, user_id: Any) -> int:
        return await self.db[C.NOTIFICATIONS].count_documents({"user_id": str(user_id), "is_read": False})

    async def mark_read(self, user_id: Any, notification_id: str) -> dict:
        doc = await self.db[C.NOTIFICATIONS].find_one_and_update(
            {"_id": oid(notification_id), "user_id": str(user_id)},  # ownership enforced in the filter
            {"$set": {"is_read": True}},
            return_document=True,
        )
        if doc is None:
            raise NotFoundError("Notification not found")
        return doc

    async def mark_all_read(self, user_id: Any) -> int:
        res = await self.db[C.NOTIFICATIONS].update_many(
            {"user_id": str(user_id), "is_read": False}, {"$set": {"is_read": True, "read_at": utcnow()}}
        )
        return res.modified_count
