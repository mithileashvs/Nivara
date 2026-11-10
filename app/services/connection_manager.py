"""WebSocket connection manager for real-time notification delivery."""
import asyncio
import logging
from typing import Any

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger("nivara.websocket")


class NotificationConnectionManager:
    """Manages active authenticated WebSocket connections for real-time notifications.
    Supports multiple simultaneous connections per user (e.g. across multiple tabs or devices).
    """

    def __init__(self) -> None:
        self.active_connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Accept the WebSocket and register it for the user."""
        await websocket.accept()
        uid = str(user_id)
        async with self._lock:
            if uid not in self.active_connections:
                self.active_connections[uid] = set()
            self.active_connections[uid].add(websocket)
        logger.debug("WebSocket client connected for user=%s (active tabs: %d)", uid, len(self.active_connections[uid]))

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Unregister the WebSocket when closed."""
        uid = str(user_id)
        async with self._lock:
            if uid in self.active_connections:
                self.active_connections[uid].discard(websocket)
                if not self.active_connections[uid]:
                    del self.active_connections[uid]
        logger.debug("WebSocket client disconnected for user=%s", uid)

    async def send_personal_notification(self, user_id: str, notification: dict[str, Any]) -> None:
        """Send a real-time notification payload to all active connections of a user."""
        uid = str(user_id)
        async with self._lock:
            sockets = list(self.active_connections.get(uid, []))

        if not sockets:
            logger.debug("No active WebSocket connections for user=%s; notification stored in DB", uid)
            return

        dead_sockets: list[WebSocket] = []
        payload = jsonable_encoder({
            "event": "notification",
            "data": notification,
        })

        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed delivering WebSocket notification to user=%s: %s", uid, exc)
                dead_sockets.append(ws)

        if dead_sockets:
            async with self._lock:
                if uid in self.active_connections:
                    for ws in dead_sockets:
                        self.active_connections[uid].discard(ws)
                    if not self.active_connections[uid]:
                        del self.active_connections[uid]

    async def broadcast_system_announcement(self, announcement: dict[str, Any]) -> None:
        """Broadcast a system announcement to all active connections platform-wide."""
        async with self._lock:
            all_sockets = [ws for ws_set in self.active_connections.values() for ws in ws_set]

        payload = jsonable_encoder({
            "event": "system_announcement",
            "data": announcement,
        })

        for ws in all_sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                pass


# Global singleton manager instance
notification_manager = NotificationConnectionManager()
