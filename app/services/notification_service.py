import logging
from typing import Any

from app.core.errors import BadRequestError, NotFoundError
from app.database.collections import C
from app.database.session import DuplicateKeyError
from app.models.engagement import Notification
from app.models.enums import NotificationCategory, NotificationType
from app.schemas.engagement import NotificationPreferencesUpdate
from app.services.connection_manager import notification_manager
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate
from app.utils.serialization import to_api
from app.utils.time_utils import utcnow

logger = logging.getLogger("nivara.notifications")

# Category mapping lookup
CATEGORY_MAP: dict[str, str] = {
    NotificationType.APPOINTMENT_REQUESTED.value: NotificationCategory.APPOINTMENT.value,
    NotificationType.APPOINTMENT_ACCEPTED.value: NotificationCategory.APPOINTMENT.value,
    NotificationType.APPOINTMENT_REJECTED.value: NotificationCategory.APPOINTMENT.value,
    NotificationType.APPOINTMENT_REMINDER.value: NotificationCategory.APPOINTMENT.value,
    NotificationType.APPOINTMENT_RESCHEDULED.value: NotificationCategory.RESCHEDULING.value,
    NotificationType.RESCHEDULE_REQUESTED.value: NotificationCategory.RESCHEDULING.value,
    NotificationType.RESCHEDULE_APPROVED.value: NotificationCategory.RESCHEDULING.value,
    NotificationType.RESCHEDULE_REJECTED.value: NotificationCategory.RESCHEDULING.value,
    NotificationType.APPOINTMENT_CANCELLED.value: NotificationCategory.CANCELLATION.value,
    NotificationType.WAITLIST_SLOT_AVAILABLE.value: NotificationCategory.WAITLIST.value,
    NotificationType.WAITLIST_ELIGIBLE.value: NotificationCategory.WAITLIST.value,
    NotificationType.WAITLIST_EXPIRED.value: NotificationCategory.WAITLIST.value,
    NotificationType.WAITLIST_OFFER_AVAILABLE.value: NotificationCategory.WAITLIST.value,
    NotificationType.WAITLIST_OFFER_ACCEPTED.value: NotificationCategory.WAITLIST.value,
    NotificationType.WAITLIST_OFFER_DECLINED.value: NotificationCategory.WAITLIST.value,
    NotificationType.DOCTOR_VERIFIED.value: NotificationCategory.SYSTEM.value,
    NotificationType.DOCTOR_SUSPENDED.value: NotificationCategory.SYSTEM.value,
    NotificationType.ACCOUNT_STATUS_CHANGED.value: NotificationCategory.SYSTEM.value,
    NotificationType.SYSTEM_ANNOUNCEMENT.value: NotificationCategory.SYSTEM.value,
    NotificationType.SECURITY_ALERT.value: NotificationCategory.SYSTEM.value,
}

# Mapping between preference schema keys and NotificationCategory
PREF_KEY_TO_CATEGORY: dict[str, str] = {
    "appointment_updates": NotificationCategory.APPOINTMENT.value,
    "rescheduling_updates": NotificationCategory.RESCHEDULING.value,
    "cancellation_updates": NotificationCategory.CANCELLATION.value,
    "waitlist_updates": NotificationCategory.WAITLIST.value,
    "system_announcements": NotificationCategory.SYSTEM.value,
}

CATEGORY_TO_PREF_KEY: dict[str, str] = {v: k for k, v in PREF_KEY_TO_CATEGORY.items()}

# Critical notifications that should never be suppressed by user preference
CRITICAL_TYPES: set[str] = {
    NotificationType.APPOINTMENT_ACCEPTED.value,
    NotificationType.APPOINTMENT_CANCELLED.value,
    NotificationType.RESCHEDULE_APPROVED.value,
    NotificationType.RESCHEDULE_REJECTED.value,
    NotificationType.ACCOUNT_STATUS_CHANGED.value,
    NotificationType.DOCTOR_VERIFIED.value,
    NotificationType.DOCTOR_SUSPENDED.value,
    NotificationType.SECURITY_ALERT.value,
}


def infer_category(notif_type: str) -> str:
    """Determine the notification category based on its event type."""
    return CATEGORY_MAP.get(notif_type, NotificationCategory.SYSTEM.value)


class NotificationService:
    """Centralized notification management system supporting persistence, real-time WebSocket
    delivery, user preferences, and filtering across all user roles."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def is_category_enabled(self, user_id: Any, category: str, notif_type: str) -> bool:
        """Check whether the user has opted to receive notifications for this category.
        Critical events are always delivered regardless of user preference."""
        if notif_type in CRITICAL_TYPES:
            return True

        row = await self.db[C.NOTIFICATION_PREFERENCES].find_one(
            {"user_id": str(user_id), "category": category}
        )
        if row is not None:
            return bool(row.get("enabled", True))
        return True

    async def notify(
        self,
        *,
        user_id: Any,
        type: str,
        title: str,
        message: str,
        category: str | None = None,
        action_url: str | None = None,
        appointment_id: Any = None,
        data: dict | None = None,
    ) -> dict | None:
        """Create and persist a notification, check user preferences, and deliver real-time
        via WebSocket. Never raises — notification failures must never break business workflows."""
        try:
            cat = (category or infer_category(type)).upper()

            # Check user preference for this category
            enabled = await self.is_category_enabled(user_id, cat, type)
            if not enabled:
                logger.info(
                    "Skipping optional notification type=%s for user=%s due to category preference %s=disabled",
                    type,
                    user_id,
                    cat,
                )
                return None

            doc = Notification(
                user_id=str(user_id),
                type=type,
                title=title,
                message=message,
                category=cat,
                action_url=action_url,
                related_appointment_id=str(appointment_id) if appointment_id else None,
                data=data or {},
            ).to_mongo()

            await self.db[C.NOTIFICATIONS].insert_one(doc)

            # Supplementary real-time WebSocket delivery
            api_payload = to_api(doc)
            await notification_manager.send_personal_notification(str(user_id), api_payload)

            return doc
        except Exception:  # noqa: BLE001
            logger.exception("Failed to create notification type=%s user=%s", type, user_id)
            return None

    async def list_for_user(
        self,
        user_id: Any,
        params: PageParams,
        is_read: bool | None = None,
        category: str | None = None,
    ) -> tuple[list[dict], int]:
        """List paginated notifications for the authenticated user, optionally filtered
        by read status and category."""
        query: dict[str, Any] = {"user_id": str(user_id)}
        if is_read is not None:
            query["is_read"] = is_read
        if category:
            query["category"] = category.upper()

        return await paginate(
            self.db[C.NOTIFICATIONS], query, params, sort=[("created_at", -1), ("_id", -1)]
        )

    async def unread_count(self, user_id: Any, category: str | None = None) -> int:
        """Count unread notifications for a user, optionally by category."""
        query: dict[str, Any] = {"user_id": str(user_id), "is_read": False}
        if category:
            query["category"] = category.upper()
        return await self.db[C.NOTIFICATIONS].count_documents(query)

    async def mark_read(self, user_id: Any, notification_id: str) -> dict:
        """Mark a single notification as read, enforcing user ownership."""
        now = utcnow()
        doc = await self.db[C.NOTIFICATIONS].find_one_and_update(
            {"_id": oid(notification_id), "user_id": str(user_id)},
            {"$set": {"is_read": True, "read_at": now, "updated_at": now}},
            return_document=True,
        )
        if doc is None:
            raise NotFoundError("Notification not found")
        return doc

    async def mark_all_read(self, user_id: Any, category: str | None = None) -> int:
        """Mark all unread notifications for a user as read."""
        query: dict[str, Any] = {"user_id": str(user_id), "is_read": False}
        if category:
            query["category"] = category.upper()

        now = utcnow()
        res = await self.db[C.NOTIFICATIONS].update_many(
            query, {"$set": {"is_read": True, "read_at": now, "updated_at": now}}
        )
        return res.modified_count

    async def delete_notification(self, user_id: Any, notification_id: str) -> None:
        """Delete / dismiss a notification, enforcing recipient ownership."""
        res = await self.db[C.NOTIFICATIONS].delete_one(
            {"_id": oid(notification_id), "user_id": str(user_id)}
        )
        if res.deleted_count == 0:
            raise NotFoundError("Notification not found")

    async def get_preferences(self, user_id: Any) -> dict[str, Any]:
        """Fetch notification preferences for a user, defaulting to all categories enabled."""
        cursor = self.db[C.NOTIFICATION_PREFERENCES].find({"user_id": str(user_id)})
        rows = await cursor.to_list(100)

        # Default all categories to True
        categories: dict[str, bool] = {cat.value: True for cat in NotificationCategory}
        for row in rows:
            cat = str(row.get("category", "")).upper()
            if cat in categories:
                categories[cat] = bool(row.get("enabled", True))

        return {
            "appointment_updates": categories.get(NotificationCategory.APPOINTMENT.value, True),
            "rescheduling_updates": categories.get(NotificationCategory.RESCHEDULING.value, True),
            "cancellation_updates": categories.get(NotificationCategory.CANCELLATION.value, True),
            "waitlist_updates": categories.get(NotificationCategory.WAITLIST.value, True),
            "system_announcements": categories.get(NotificationCategory.SYSTEM.value, True),
            "categories": categories,
        }

    async def update_preferences(
        self, user_id: Any, payload: NotificationPreferencesUpdate
    ) -> dict[str, Any]:
        """Upsert notification preferences for a user."""
        uid = str(user_id)
        now = utcnow()

        # Build category -> enabled updates
        updates: dict[str, bool] = {}

        if payload.appointment_updates is not None:
            updates[NotificationCategory.APPOINTMENT.value] = payload.appointment_updates
        if payload.rescheduling_updates is not None:
            updates[NotificationCategory.RESCHEDULING.value] = payload.rescheduling_updates
        if payload.cancellation_updates is not None:
            updates[NotificationCategory.CANCELLATION.value] = payload.cancellation_updates
        if payload.waitlist_updates is not None:
            updates[NotificationCategory.WAITLIST.value] = payload.waitlist_updates
        if payload.system_announcements is not None:
            updates[NotificationCategory.SYSTEM.value] = payload.system_announcements

        valid_cats = {c.value for c in NotificationCategory}
        if payload.categories:
            for cat, val in payload.categories.items():
                cat_key = str(cat).strip().upper()
                if cat_key not in valid_cats:
                    raise BadRequestError(
                        f"Unsupported notification category: {cat}",
                        code="invalid_notification_category",
                    )
                updates[cat_key] = bool(val)

        for cat, enabled in updates.items():
            filter_doc = {"user_id": uid, "category": cat}
            update_doc = {
                "$set": {"enabled": enabled, "updated_at": now},
                "$setOnInsert": {"user_id": uid, "category": cat, "created_at": now},
            }
            try:
                await self.db[C.NOTIFICATION_PREFERENCES].update_one(
                    filter_doc, update_doc, upsert=True
                )
            except DuplicateKeyError:
                await self.db[C.NOTIFICATION_PREFERENCES].update_one(
                    filter_doc, {"$set": {"enabled": enabled, "updated_at": now}}
                )

        return await self.get_preferences(user_id)
