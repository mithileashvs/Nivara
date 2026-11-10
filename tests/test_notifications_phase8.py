"""Phase 8 Real-Time WebSocket Notifications, Category Preferences & Suppression Suite."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from app.models.enums import NotificationType
from app.services.connection_manager import notification_manager
from app.services.notification_service import NotificationService


async def test_notification_preferences_upsert_partial_concurrent_and_invalid_category(world):
    # Default preferences are all True
    r_def = await world.api("GET", "/notifications/preferences", world.p1)
    assert r_def.status_code == 200
    body = r_def.json()
    assert body["appointment_updates"] is True
    assert body["waitlist_updates"] is True
    assert body["system_announcements"] is True
    assert body["categories"]["WAITLIST"] is True

    # Partial update modifies only waitlist_updates
    r_upd = await world.api("PUT", "/notifications/preferences", world.p1, json={"waitlist_updates": False})
    assert r_upd.status_code == 200
    assert r_upd.json()["waitlist_updates"] is False
    assert r_upd.json()["appointment_updates"] is True
    assert r_upd.json()["categories"]["WAITLIST"] is False

    # Invalid category via categories map returns 400 invalid_notification_category
    r_bad = await world.api(
        "PUT",
        "/notifications/preferences",
        world.p1,
        json={"categories": {"NON_EXISTENT_CATEGORY": False}},
    )
    assert r_bad.status_code == 400
    assert r_bad.json()["error"]["code"] == "invalid_notification_category"

    # Concurrent upsert race on fresh preferences for p2 succeeds cleanly without DuplicateKeyError
    results = await asyncio.gather(
        world.api("PUT", "/notifications/preferences", world.p2, json={"appointment_updates": False}),
        world.api("PUT", "/notifications/preferences", world.p2, json={"waitlist_updates": False}),
        world.api("PUT", "/notifications/preferences", world.p2, json={"system_announcements": False}),
        return_exceptions=True,
    )
    assert all(not isinstance(r, Exception) and r.status_code == 200 for r in results), results
    p2_prefs = (await world.api("GET", "/notifications/preferences", world.p2)).json()
    assert p2_prefs["appointment_updates"] is False
    assert p2_prefs["waitlist_updates"] is False
    assert p2_prefs["system_announcements"] is False


async def test_notification_suppression_optional_vs_critical_and_waitlist_categories(world):
    # Disable optional WAITLIST and SYSTEM categories for p1
    r_pref = await world.api(
        "PUT",
        "/notifications/preferences",
        world.p1,
        json={"waitlist_updates": False, "system_announcements": False},
    )
    assert r_pref.status_code == 200

    svc = NotificationService(world.db)

    # Optional categories are suppressed when disabled
    skipped_sys = await svc.notify(
        user_id=world.p1.user_id,
        type=NotificationType.SYSTEM_ANNOUNCEMENT.value,
        title="Maintenance Window",
        message="Scheduled upgrade tonight.",
    )
    assert skipped_sys is None

    skipped_wl = await svc.notify(
        user_id=world.p1.user_id,
        type=NotificationType.WAITLIST_OFFER_AVAILABLE.value,
        title="Waitlist Offer",
        message="Slot open.",
    )
    assert skipped_wl is None

    # Critical events NEVER suppressed even if SYSTEM / APPOINTMENT / CANCELLATION disabled
    await world.api(
        "PUT",
        "/notifications/preferences",
        world.p1,
        json={"appointment_updates": False, "cancellation_updates": False, "rescheduling_updates": False},
    )
    delivered_cancel = await svc.notify(
        user_id=world.p1.user_id,
        type=NotificationType.APPOINTMENT_CANCELLED.value,
        title="Cancelled",
        message="Cancelled by clinic.",
    )
    delivered_sec = await svc.notify(
        user_id=world.p1.user_id,
        type=NotificationType.SECURITY_ALERT.value,
        title="Security Notice",
        message="Important alert.",
    )
    assert delivered_cancel is not None and delivered_cancel["type"] == "APPOINTMENT_CANCELLED"
    assert delivered_sec is not None and delivered_sec["type"] == "SECURITY_ALERT"

    # Re-enable waitlist updates and verify WAITLIST_OFFER_* map into WAITLIST category
    await world.api("PUT", "/notifications/preferences", world.p1, json={"waitlist_updates": True})
    for wt in (
        NotificationType.WAITLIST_OFFER_AVAILABLE.value,
        NotificationType.WAITLIST_OFFER_ACCEPTED.value,
        NotificationType.WAITLIST_OFFER_DECLINED.value,
    ):
        created = await svc.notify(
            user_id=world.p1.user_id,
            type=wt,
            title=wt,
            message="Waitlist update",
        )
        assert created is not None and created["category"] == "WAITLIST"


async def test_websocket_auth_ping_pong_and_realtime_notification_push(world):
    # Prepare an available slot in PostgreSQL for live appointment request push
    await world.add_window(world.d1, start="09:00", end="10:00")
    s_0900 = await world.slot_at(world.d1, "09:00")

    d1_token = world.d1.headers["Authorization"].split(" ", 1)[1]
    p3_token = world.p3.headers["Authorization"].split(" ", 1)[1]
    expired_token = jwt.encode(
        {
            "sub": world.d1.user_id,
            "role": "DOCTOR",
            "type": "access",
            "iat": datetime.now(timezone.utc) - timedelta(minutes=10),
            "exp": datetime.now(timezone.utc) - timedelta(seconds=10),
        },
        world.settings.jwt_secret.get_secret_value(),
        algorithm=world.settings.jwt_algorithm,
    )

    # Deactivate p3 so WS rejects inactive accounts with 1008
    deact = await world.api(
        "PUT",
        f"/admin/users/{world.p3.user_id}/active",
        world.admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200

    def _run_ws_suite() -> None:
        ws_app = create_app(world.settings)  # Uses isolated TestClient-loop DatabaseManager
        with TestClient(ws_app) as tc:
            # 1. Missing token -> WS 1008 policy violation
            with pytest.raises(WebSocketDisconnect) as exc_missing:
                with tc.websocket_connect("/api/v1/notifications/ws"):
                    pass
            assert exc_missing.value.code == 1008

            # 2. Expired / malformed JWT -> WS 1008
            for bad_tok in (expired_token, "not-a-jwt-token"):
                with pytest.raises(WebSocketDisconnect) as exc_bad:
                    with tc.websocket_connect(f"/api/v1/notifications/ws?token={bad_tok}"):
                        pass
                assert exc_bad.value.code == 1008

            # 3. Deactivated user -> WS 1008
            with pytest.raises(WebSocketDisconnect) as exc_inactive:
                with tc.websocket_connect(f"/api/v1/notifications/ws?token={p3_token}"):
                    pass
            assert exc_inactive.value.code == 1008

            # 4. Valid doctor JWT -> initial connected ACK, ping/pong, and live notification push on booking
            with tc.websocket_connect(f"/api/v1/notifications/ws?token={d1_token}") as ws:
                ack = ws.receive_json()
                assert ack["event"] == "connected"
                assert ack["user_id"] == world.d1.user_id
                assert isinstance(ack["unread"], int)

                ws.send_text("ping")
                assert ws.receive_text() == "pong"

                r_book = tc.post(
                    "/api/v1/appointments",
                    headers=world.p1.headers,
                    json={"slot_id": s_0900["id"], "consultation_type": "FIRST_VISIT"},
                )
                assert r_book.status_code == 201, r_book.text

                push = ws.receive_json()
                assert push["event"] == "notification"
                assert push["data"]["type"] == "APPOINTMENT_REQUESTED"
                assert push["data"]["category"] == "APPOINTMENT"

    notification_manager.active_connections.clear()
    notification_manager._lock = asyncio.Lock()
    try:
        await asyncio.to_thread(_run_ws_suite)
    finally:
        # Leave notification_manager completely clean across event loops
        notification_manager.active_connections.clear()
        notification_manager._lock = asyncio.Lock()
