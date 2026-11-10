"""Phase 8 Security, JWT, RBAC, Hospital-Scoping, Proxy-IP, IDOR & Startup Validation Suite."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import jwt
import pytest
from pydantic import ValidationError

from app.core.audit_context import resolve_client_ip
from app.core.config import Settings
from app.main import create_app
from tests.conftest import make_settings

VALID_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


# ---------------------------------------------------------------------------
# 1. JWT Validation & Session Security
# ---------------------------------------------------------------------------


async def test_jwt_expired_wrong_secret_alg_none_and_wrong_type(world):
    base_claims = {
        "sub": world.p1.user_id,
        "role": "PATIENT",
        "type": "access",
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
    }
    expired_tok = jwt.encode(base_claims, world.settings.jwt_secret.get_secret_value(), algorithm="HS256")
    r_exp = await world.api("GET", "/auth/me", headers={"Authorization": f"Bearer {expired_tok}"})
    assert r_exp.status_code == 401, r_exp.text
    assert r_exp.json()["error"]["code"] == "token_expired"

    wrong_sig_claims = {
        **base_claims,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    wrong_sig_tok = jwt.encode(wrong_sig_claims, "completely-different-secret-key-999999", algorithm="HS256")
    r_sig = await world.api("GET", "/auth/me", headers={"Authorization": f"Bearer {wrong_sig_tok}"})
    assert r_sig.status_code == 401, r_sig.text
    assert r_sig.json()["error"]["code"] == "invalid_token"

    # alg=none token must be rejected
    alg_none_tok = jwt.encode(wrong_sig_claims, key=None, algorithm="none")
    r_none = await world.api("GET", "/auth/me", headers={"Authorization": f"Bearer {alg_none_tok}"})
    assert r_none.status_code == 401, r_none.text
    assert r_none.json()["error"]["code"] == "invalid_token"

    # wrong token type claim
    refresh_claims = {**wrong_sig_claims, "type": "refresh"}
    bad_type_tok = jwt.encode(refresh_claims, world.settings.jwt_secret.get_secret_value(), algorithm="HS256")
    r_type = await world.api("GET", "/auth/me", headers={"Authorization": f"Bearer {bad_type_tok}"})
    assert r_type.status_code == 401, r_type.text


async def test_security_headers_and_no_password_leak(world):
    r = await world.api("GET", "/auth/me", world.p1)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "password" not in body and "password_hash" not in body
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "no-referrer"
    assert "no-store" in (r.headers.get("cache-control") or "")
    assert r.headers.get("x-request-id")


# ---------------------------------------------------------------------------
# 2. Full Phase 1-6 RBAC Matrix
# ---------------------------------------------------------------------------


async def test_phase1_to_6_rbac_matrix(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    new_slot = await world.slot_at(world.d1, "09:30")
    r = await world.api(
        "POST",
        f"/appointments/{appt['id']}/reschedule",
        world.p1,
        json={"new_slot_id": new_slot["id"], "reason": "Earlier conflict"},
    )
    assert r.status_code == 200, r.text
    req_list = (await world.api("GET", f"/appointments/{appt['id']}/reschedule-requests", world.p1)).json()
    req_id = req_list[0]["id"]

    # Reschedule requests RBAC: patient & admin cannot approve/reject; admin cannot view participant req; wrong doctor/patient gets 404
    for actor, expected in ((world.p1, 403), (world.admin, 403)):
        r1 = await world.api("POST", f"/reschedule-requests/{req_id}/approve", actor, json={})
        assert r1.status_code == expected, r1.text
        r2 = await world.api("POST", f"/reschedule-requests/{req_id}/reject", actor, json={})
        assert r2.status_code == expected, r2.text
    assert (await world.api("GET", f"/reschedule-requests/{req_id}", world.admin)).status_code == 403
    assert (await world.api("GET", f"/reschedule-requests/{req_id}", world.p2)).status_code == 404
    assert (await world.api("GET", f"/reschedule-requests/{req_id}", world.d2)).status_code == 404

    # Waitlist RBAC
    wl_payload = {
        "doctor_id": world.d1.id,
        "date_from": world.tomorrow.isoformat(),
        "date_to": world.tomorrow.isoformat(),
    }
    assert (await world.api("POST", "/waitlist", world.d1, json=wl_payload)).status_code == 403
    assert (await world.api("POST", "/waitlist", world.admin, json=wl_payload)).status_code == 403
    assert (await world.api("GET", "/doctors/me/waitlist", world.p1)).status_code == 403
    assert (await world.api("GET", "/doctors/me/waitlist/statistics", world.admin)).status_code == 403
    assert (await world.api("GET", "/admin/waitlist", world.p1)).status_code == 403
    assert (await world.api("GET", "/admin/waitlist/statistics", world.d1)).status_code == 403

    # Medical records RBAC
    files = {"file": ("lab.png", VALID_PNG, "image/png")}
    data = {"title": "Lab Result", "category": "LAB_REPORT"}
    for actor in (world.d1, world.admin):
        ru = await world.api("POST", "/medical-records/documents/upload", actor, files=files, data=data)
        assert ru.status_code == 403, ru.text
    up = await world.api("POST", "/medical-records/documents/upload", world.p1, files=files, data=data)
    assert up.status_code == 201, up.text
    doc_id = up.json()["id"]

    assert (await world.api("GET", f"/medical-records/documents/{doc_id}/download", world.admin)).status_code == 403
    assert (await world.api("GET", "/medical-records/timeline", world.admin)).status_code == 403
    assert (await world.api("GET", "/medical-records/audits", world.d1)).status_code == 403
    assert (await world.api("GET", "/medical-records/admin/stats", world.p1)).status_code == 403
    assert (await world.api("GET", "/medical-records/admin/stats", world.d1)).status_code == 403
    assert (await world.api("GET", "/medical-records/shared", world.p1)).status_code == 403
    assert (await world.api("GET", "/medical-records/shared", world.admin)).status_code == 403

    # Analytics RBAC
    for actor in (world.p1, world.d1):
        assert (await world.api("GET", "/analytics/overview", actor)).status_code == 403
        assert (await world.api("GET", "/analytics/hospitals", actor)).status_code == 403
        assert (await world.api("GET", "/analytics/reports/export", actor)).status_code == 403

    # Centralized Audit & Security Activity RBAC (patient/doctor blocked; hospital admin blocked on platform-only endpoints)
    for actor in (world.p1, world.d1):
        assert (await world.api("GET", "/admin/audit-logs", actor)).status_code == 403
        assert (await world.api("GET", "/admin/audit-logs/export", actor)).status_code == 403
        assert (await world.api("GET", "/admin/security/activity", actor)).status_code == 403
    assert (await world.api("GET", "/admin/doctor-verification", world.h1_admin)).status_code == 403


# ---------------------------------------------------------------------------
# 3. Hospital-Scoped Admin Isolation (0, 1, and 2 Hospitals)
# ---------------------------------------------------------------------------


async def test_hospital_scoped_admin_isolation_across_0_1_and_2_hospitals(world):
    h1_id = world.hospital["h1"]["id"]
    h2_id = world.hospital["h2"]["id"]

    empty_admin = await world.create_admin_direct("emptyadmin@smartcare-demo.com", managed_hospital_ids=[])
    two_hosp_admin = await world.create_admin_direct("twohosp@smartcare-demo.com", managed_hospital_ids=[h1_id, h2_id])

    await world.add_window(world.d1, hospital="h1", dept="h1_general")
    await world.add_window(world.d3, hospital="h2", dept="h2_general")
    await world.book(world.p1, world.d1, "09:00", confirm=True)
    await world.book(world.p2, world.d3, "10:00", confirm=True)

    # Create waitlist entries in H1 and H2
    wl_h1 = await world.api("POST", "/waitlist", world.p1, json={
        "hospital_id": h1_id, "date_from": world.tomorrow.isoformat(), "date_to": world.tomorrow.isoformat(),
    })
    assert wl_h1.status_code == 201, wl_h1.text
    wl_h2 = await world.api("POST", "/waitlist", world.p2, json={
        "hospital_id": h2_id, "date_from": world.tomorrow.isoformat(), "date_to": world.tomorrow.isoformat(),
    })
    assert wl_h2.status_code == 201, wl_h2.text

    # 0-hospital admin MUST see empty lists/zeros and NEVER full platform data
    r_appts_empty = await world.api("GET", "/admin/appointments", empty_admin)
    assert r_appts_empty.status_code == 200 and r_appts_empty.json()["total"] == 0
    r_wl_empty = await world.api("GET", "/admin/waitlist", empty_admin)
    assert r_wl_empty.status_code == 200 and r_wl_empty.json()["total"] == 0
    r_wls_empty = await world.api("GET", "/admin/waitlist/statistics", empty_admin)
    assert r_wls_empty.status_code == 200 and r_wls_empty.json()["total_active_entries"] == 0
    r_an_empty = await world.api("GET", "/analytics/overview", empty_admin)
    assert r_an_empty.status_code == 200 and r_an_empty.json()["accessible_hospitals"] == 0
    r_audit_empty = await world.api("GET", "/admin/audit-logs", empty_admin)
    assert r_audit_empty.status_code == 200 and r_audit_empty.json()["total"] == 0

    # 1-hospital admin (h1_admin) only sees H1 and gets 403 on explicit H2 filter
    r_wl_h1 = await world.api("GET", "/admin/waitlist", world.h1_admin)
    assert r_wl_h1.status_code == 200
    assert {e["hospital_id"] for e in r_wl_h1.json()["items"]} == {h1_id}
    assert (await world.api("GET", f"/admin/waitlist?hospital_id={h2_id}", world.h1_admin)).status_code == 403

    r_wls_h1 = await world.api("GET", "/admin/waitlist/statistics", world.h1_admin)
    assert r_wls_h1.status_code == 200
    assert set(r_wls_h1.json()["hospital_breakdown"].keys()) == {h1_id}

    assert (await world.api("GET", f"/analytics/hospitals/{h2_id}", world.h1_admin)).status_code == 403
    assert (await world.api("GET", f"/admin/audit-logs?hospital_id={h2_id}", world.h1_admin)).status_code == 403
    assert (await world.api("GET", f"/admin/audit-logs/export?hospital_id={h2_id}", world.h1_admin)).status_code == 403
    assert (await world.api("GET", f"/admin/security/activity?hospital_id={h2_id}", world.h1_admin)).status_code == 403

    r_audit_h1 = await world.api("GET", "/admin/audit-logs", world.h1_admin)
    assert r_audit_h1.status_code == 200
    assert all(item["hospital_id"] == h1_id for item in r_audit_h1.json()["items"])

    # 2-hospital admin sees both H1 and H2
    r_wl_both = await world.api("GET", "/admin/waitlist", two_hosp_admin)
    assert r_wl_both.status_code == 200
    assert {e["hospital_id"] for e in r_wl_both.json()["items"]} == {h1_id, h2_id}
    r_an_both = await world.api("GET", "/analytics/overview", two_hosp_admin)
    assert r_an_both.status_code == 200 and r_an_both.json()["accessible_hospitals"] == 2
    r_audit_both = await world.api("GET", "/admin/audit-logs", two_hosp_admin)
    assert r_audit_both.status_code == 200
    assert {item["hospital_id"] for item in r_audit_both.json()["items"]} <= {h1_id, h2_id}


# ---------------------------------------------------------------------------
# 4. IDOR & Malformed UUID / 24-Hex Legacy ID Handling (Zero 500s)
# ---------------------------------------------------------------------------


async def test_malformed_ids_and_24hex_ids_return_clean_4xx(world):
    bad_uuid = "not-a-valid-uuid"
    hex24 = "6ab0ce6703a2b6aff2b977df"
    random_uuid = str(uuid4())

    # Medical documents
    assert (await world.api("GET", f"/medical-records/documents/{bad_uuid}", world.p1)).status_code == 400
    assert (await world.api("GET", f"/medical-records/documents/{hex24}", world.p1)).status_code == 404
    assert (await world.api("GET", f"/medical-records/documents/{random_uuid}/download", world.p1)).status_code == 404
    assert (await world.api("DELETE", f"/medical-records/documents/{bad_uuid}", world.p1)).status_code == 400
    assert (await world.api("GET", f"/medical-records/patients/{bad_uuid}/timeline", world.d1)).status_code == 400
    assert (await world.api("GET", f"/medical-records/patients/{hex24}/timeline", world.d1)).status_code == 403
    assert (await world.api("GET", f"/medical-records/shared?patient_id={bad_uuid}", world.d1)).status_code == 400
    assert (await world.api("GET", f"/medical-records/audits?patient_id={bad_uuid}", world.admin)).status_code == 400

    # Waitlist
    assert (await world.api("GET", f"/waitlist/{bad_uuid}", world.p1)).status_code == 422
    assert (await world.api("GET", f"/waitlist/{hex24}", world.p1)).status_code == 404
    assert (await world.api("POST", f"/waitlist/offers/{hex24}/accept", world.p1, json={})).status_code == 404
    assert (await world.api("POST", f"/waitlist/offers/{bad_uuid}/decline", world.p1, json={})).status_code == 422
    assert (await world.api("GET", f"/admin/waitlist?hospital_id={bad_uuid}", world.admin)).status_code == 400

    # Audit logs
    assert (await world.api("GET", f"/admin/audit-logs/{bad_uuid}", world.admin)).status_code == 422
    assert (await world.api("GET", f"/admin/audit-logs/{random_uuid}", world.admin)).status_code == 404
    assert (await world.api("GET", f"/admin/audit-logs?hospital_id={bad_uuid}", world.admin)).status_code == 400


# ---------------------------------------------------------------------------
# 5. Trusted Proxy IP Handling & Rate Limit Spoofing Resistance
# ---------------------------------------------------------------------------


def test_resolve_client_ip_trusted_proxy_and_spoof_resistance():
    # Untrusted by default -> XFF/X-Real-IP completely ignored
    s_default = make_settings(trust_proxy_headers=False, trusted_proxy_ips=["10.0.0.0/8"])
    assert (
        resolve_client_ip("198.51.100.2", x_forwarded_for="1.2.3.4", x_real_ip="5.6.7.8", settings=s_default)
        == "198.51.100.2"
    )

    # Trusted enabled, but direct socket peer is NOT in trusted_proxy_ips -> headers ignored
    s_trusted = make_settings(trust_proxy_headers=True, trusted_proxy_ips=["10.0.0.0/8", "127.0.0.1/32"])
    assert (
        resolve_client_ip("198.51.100.2", x_forwarded_for="203.0.113.10", settings=s_trusted)
        == "198.51.100.2"
    )

    # Direct peer IS trusted proxy: scans right-to-left skipping trusted proxy hops so left-side spoof is ignored
    assert (
        resolve_client_ip(
            "10.1.2.3",
            x_forwarded_for="8.8.8.8, 203.0.113.45:51234, 10.2.3.4",
            settings=s_trusted,
        )
        == "203.0.113.45"
    )

    # Bracketed IPv6 with port & X-Real-IP fallback
    assert resolve_client_ip("127.0.0.1", x_forwarded_for="[2001:db8::9]:8443", settings=s_trusted) == "2001:db8::9"
    assert resolve_client_ip("127.0.0.1", x_real_ip="192.0.2.77", settings=s_trusted) == "192.0.2.77"

    # Malformed headers never raise
    assert resolve_client_ip("127.0.0.1", x_forwarded_for="not_an_ip, ???", settings=s_trusted) == "127.0.0.1"

    # Wildcard '*' MUST be rejected
    with pytest.raises(ValidationError):
        make_settings(trust_proxy_headers=True, trusted_proxy_ips=["*"])


async def test_rate_limiter_cannot_be_bypassed_via_spoofed_xff(db):
    custom_settings = make_settings(
        rate_limit_enabled=True,
        rate_limit_auth_per_minute=2,
        trust_proxy_headers=False,
        trusted_proxy_ips=[],
    )
    app = create_app(custom_settings, db=db)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for i, spoof_ip in enumerate(("1.1.1.1", "2.2.2.2")):
            r = await client.post(
                "/api/v1/auth/login",
                json={"email": f"nobody{i}@test.com", "password": "WrongPassword!1"},
                headers={"X-Forwarded-For": spoof_ip, "X-Real-IP": spoof_ip},
            )
            assert r.status_code == 401, r.text

        # 3rd request from a DIFFERENT spoofed XFF must still be rate-limited because direct client is identical
        r3 = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody3@test.com", "password": "WrongPassword!1"},
            headers={"X-Forwarded-For": "9.9.9.9", "X-Real-IP": "9.9.9.9"},
        )
        assert r3.status_code == 429, r3.text
        assert r3.json()["error"]["code"] == "rate_limited"
        assert int(r3.headers["retry-after"]) >= 1


# ---------------------------------------------------------------------------
# 6. Production Config Safety & Ephemeral Storage Startup Warning
# ---------------------------------------------------------------------------


def test_production_config_validation_rejects_unsafe_defaults():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", jwt_secret="short-secret", cors_origins=["https://app.example.com"])

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="x" * 40,
            cors_origins=["*"],
        )

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="x" * 40,
            document_storage_provider="supabase",
            supabase_url=None,
            supabase_service_role_key=None,
        )


async def test_production_local_storage_emits_critical_startup_warning(db, caplog):
    prod_settings = make_settings(
        environment="production",
        jwt_secret="super-strong-production-secret-key-at-least-32-chars",
        cors_origins=["https://nivara-brown.vercel.app"],
        document_storage_provider="local",
        background_jobs_enabled=False,
    )
    app = create_app(prod_settings, db=db)
    with caplog.at_level(logging.CRITICAL, logger="nivara"):
        async with app.router.lifespan_context(app):
            pass
    assert any("CRITICAL STORAGE WARNING" in rec.message for rec in caplog.records)
