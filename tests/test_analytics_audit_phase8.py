"""Phase 8 Operational Analytics Formulas, CSV Security, Audit Immutability & Threat Detection Suite."""
from __future__ import annotations

import csv
import io
from datetime import timedelta

from app.models.enums import AuditAction, AuditActorRole, AuditEntityType
from app.services.analytics_service import FORMULA_DEFINITIONS
from app.services.audit_service import AuditService, sanitize_metadata
from tests.helpers import today_utc


async def test_analytics_overview_formulas_status_hospital_dept_doctor_and_no_pii(world):
    # Seed slots in h1 (d1) on tomorrow to exercise EVERY appointment status in one scope
    await world.add_window(world.d1, hospital="h1", dept="h1_general", start="09:00", end="13:00", duration=30)
    await world.add_window(world.d3, hospital="h2", dept="h2_general", start="14:00", end="15:00", duration=30)

    # 1. REQUESTED (09:00)
    await world.book(world.p1, world.d1, "09:00", confirm=False)

    # 2. REJECTED (09:30)
    a_rej = await world.book(world.p2, world.d1, "09:30", confirm=False)
    assert (await world.api("POST", f"/appointments/{a_rej['id']}/reject", world.d1, json={"reason": "Unavailable"})).status_code == 200

    # 3. CONFIRMED (10:00)
    await world.book(world.p3, world.d1, "10:00", confirm=True)

    # 4. COMPLETED (10:30)
    a_comp = await world.book(world.p1, world.d1, "10:30", confirm=True)
    await world.make_started(a_comp["id"])
    assert (await world.api("POST", f"/appointments/{a_comp['id']}/complete", world.d1, json={})).status_code == 200

    # 5. NO_SHOW (11:00)
    a_ns = await world.book(world.p2, world.d1, "11:00", confirm=True)
    await world.make_started(a_ns["id"])
    assert (await world.api("POST", f"/appointments/{a_ns['id']}/no-show", world.d1, json={})).status_code == 200

    # 6. CANCELLED (11:30)
    a_canc = await world.book(world.p3, world.d1, "11:30", confirm=True)
    assert (await world.api("POST", f"/appointments/{a_canc['id']}/cancel", world.p3, json={"reason": "Reschedule needed"})).status_code == 200

    # 7. RESCHEDULE_REQUESTED (12:00 -> 12:30)
    a_resch = await world.book(world.p2, world.d1, "12:00", confirm=True)
    s_1230 = await world.slot_at(world.d1, "12:30")
    r_req = await world.api(
        "POST",
        f"/appointments/{a_resch['id']}/reschedule",
        world.p2,
        json={"new_slot_id": s_1230["id"], "reason": "Prefer 12:30"},
    )
    assert r_req.status_code == 200 and r_req.json()["status"] == "RESCHEDULE_REQUESTED"

    # Also book 1 CONFIRMED in h2 (d3) to verify strict hospital scoping vs platform totals
    await world.book(world.p1, world.d3, "14:00", confirm=True)

    d_from = (today_utc() - timedelta(days=2)).isoformat()
    d_to = (world.tomorrow + timedelta(days=1)).isoformat()
    q = f"preset=custom&date_from={d_from}&date_to={d_to}"

    # Verify h1-scoped admin analytics match exact Phase 5 final formulas
    # h1 has: REQUESTED=1, REJECTED=1, CONFIRMED=1, RESCHEDULE_REQUESTED=1, COMPLETED=1, NO_SHOW=1, CANCELLED=1 (Total=7)
    # Denom for cancellation_rate & completion_rate = CONFIRMED(1)+RESCHEDULE(1)+COMPLETED(1)+NO_SHOW(1)+CANCELLED(1) = 5 (excludes REQUESTED & REJECTED!)
    ov_h1 = (await world.api("GET", f"/analytics/overview?{q}", world.h1_admin)).json()
    assert ov_h1["scope"] == "hospital"
    assert ov_h1["total_appointments"]["current"] == 7
    assert ov_h1["cancellation_rate"]["numerator"] == 1
    assert ov_h1["cancellation_rate"]["denominator"] == 5
    assert ov_h1["cancellation_rate"]["current"] == 20.0
    assert ov_h1["completion_rate"]["current"] == 20.0
    assert ov_h1["rejection_rate"]["current"] == 20.0  # 1 / (1+1+1+1+1)
    assert ov_h1["no_show_rate"]["current"] == 25.0  # 1 / (1+1+1+1)
    assert "REQUESTED" in ov_h1["formula_definitions"]["cancellation_rate"]
    assert ov_h1["formula_definitions"]["cancellation_rate"] == FORMULA_DEFINITIONS["cancellation_rate"]

    # Consistent cancellation_rate = 20.0 across status, hospital list, hospital detail, department & doctor endpoints
    st_h1 = (await world.api("GET", f"/analytics/appointments/status?{q}", world.h1_admin)).json()
    assert st_h1["rates"]["cancellation_rate"]["current"] == 20.0
    assert st_h1["rates"]["cancellation_rate"]["denominator"] == 5

    hosp_list = (await world.api("GET", f"/analytics/hospitals?{q}", world.h1_admin)).json()
    assert hosp_list["hospitals"]["total"] == 1
    assert hosp_list["hospitals"]["items"][0]["cancellation_rate"] == 20.0

    h1_id = world.hospital["h1"]["id"]
    h2_id = world.hospital["h2"]["id"]
    hosp_det = (await world.api("GET", f"/analytics/hospitals/{h1_id}?{q}", world.h1_admin)).json()
    assert hosp_det["hospital"]["cancellation_rate"] == 20.0
    assert (await world.api("GET", f"/analytics/hospitals/{h2_id}?{q}", world.h1_admin)).status_code == 403

    dept_res = (await world.api("GET", f"/analytics/departments?{q}&department_id={world.dept['h1_general']['id']}", world.h1_admin)).json()
    assert dept_res["departments"]["items"][0]["cancellation_rate"] == 20.0

    doc_res = (await world.api("GET", f"/analytics/doctors?{q}&doctor_id={world.d1.id}", world.h1_admin)).json()
    doc_row = doc_res["doctors"]["items"][0]
    assert doc_row["cancellation_rate"] == 20.0
    assert doc_row["total_slots"] == 8  # 09:00-13:00 in 30m increments

    # Zero-denominator check (empty future window) must safely return 0.0
    empty_from = (world.tomorrow + timedelta(days=20)).isoformat()
    empty_to = (world.tomorrow + timedelta(days=22)).isoformat()
    ov_empty = (await world.api("GET", f"/analytics/overview?preset=custom&date_from={empty_from}&date_to={empty_to}", world.h1_admin)).json()
    assert ov_empty["total_appointments"]["current"] == 0
    assert ov_empty["cancellation_rate"]["current"] == 0.0
    assert ov_empty["completion_rate"]["current"] == 0.0

    # Patient aggregate analytics must NEVER contain patient PII
    pat_res = (await world.api("GET", f"/analytics/patients?{q}", world.h1_admin)).json()
    assert pat_res["active_patients"]["current"] == 3
    pat_blob = str(pat_res)
    for sensitive in (world.p1.email, world.p1.name, world.p2.email, world.p2.name, world.p3.email):
        assert sensitive not in pat_blob


async def test_csv_exports_formula_injection_neutralization_and_hospital_scoping(world):
    # Create hospital & department with Excel/CSV formula injection payloads
    h_inj = await world.api(
        "POST",
        "/hospitals",
        world.admin,
        json={"name": "=cmd|' /C calc'!A0 Hospital", "address": "9 Security Ln", "location": {"city": "+CITY_INJ"}},
    )
    assert h_inj.status_code == 201, h_inj.text
    h_inj_id = h_inj.json()["id"]

    d_inj = await world.api(
        "POST",
        "/departments",
        world.admin,
        json={"hospital_id": h_inj_id, "name": "@SUM(1,2) Dept"},
    )
    assert d_inj.status_code == 201, d_inj.text

    await AuditService(world.db, world.settings).log_event(
        action=AuditAction.HOSPITAL_CREATED,
        entity_type=AuditEntityType.HOSPITAL,
        entity_id=h_inj_id,
        hospital_id=h_inj_id,
        description="-1+1 Alert Triggered",
    )

    d_from = (today_utc() - timedelta(days=2)).isoformat()
    d_to = (world.tomorrow + timedelta(days=1)).isoformat()

    # Analytics CSV export neutralizes leading = / + / - / @
    r_hosp_csv = await world.api(
        "GET",
        f"/analytics/reports/export?report_type=hospital_performance&preset=custom&date_from={d_from}&date_to={d_to}",
        world.admin,
    )
    assert r_hosp_csv.status_code == 200
    assert "text/csv" in r_hosp_csv.headers.get("content-type", "")
    parsed_hosp = list(csv.reader(io.StringIO(r_hosp_csv.text)))
    inj_rows = [row for row in parsed_hosp if h_inj_id in row]
    assert len(inj_rows) == 1
    assert inj_rows[0][1].startswith("'=cmd")
    assert inj_rows[0][2].startswith("'+CITY_INJ")

    r_dept_csv = await world.api(
        "GET",
        f"/analytics/reports/export?report_type=department_performance&preset=custom&date_from={d_from}&date_to={d_to}",
        world.admin,
    )
    parsed_dept = list(csv.reader(io.StringIO(r_dept_csv.text)))
    dept_rows = [row for row in parsed_dept if d_inj.json()["id"] in row]
    assert len(dept_rows) == 1
    assert dept_rows[0][1].startswith("'@SUM(1,2)")

    # Audit log CSV export also neutralizes leading formula characters & enforces hospital scope
    r_audit_csv = await world.api("GET", "/admin/audit-logs/export", world.admin)
    assert r_audit_csv.status_code == 200
    assert "'-1+1 Alert Triggered" in r_audit_csv.text

    # h1_admin cannot export injected hospital's audit logs or analytics
    assert (await world.api("GET", f"/admin/audit-logs/export?hospital_id={h_inj_id}", world.h1_admin)).status_code == 403
    assert (await world.api("GET", f"/analytics/reports/export?report_type=hospital_performance&hospital_id={h_inj_id}", world.h1_admin)).status_code == 403


async def test_audit_logs_immutability_metadata_scrubbing_and_security_thresholds(app, world):
    # 1. Verify NO PUT/PATCH/DELETE endpoints exist for /audit-logs or /security
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if "/audit-logs" in path or "/admin/security" in path:
            assert not (methods & {"PUT", "PATCH", "DELETE"}), f"Mutable audit route found: {methods} {path}"

    logs_r = await world.api("GET", "/admin/audit-logs?page_size=5", world.admin)
    assert logs_r.status_code == 200 and logs_r.json()["total"] >= 1
    sample_id = logs_r.json()["items"][0]["id"]
    for bad_method in ("PUT", "PATCH", "DELETE"):
        assert (await world.api(bad_method, f"/admin/audit-logs/{sample_id}", world.admin)).status_code == 405

    # 2. Sanitize_metadata + persisted audit_logs strip secrets & clinical data
    raw_meta = {
        "password": "secret-pw",
        "jwt_token": "eyJhbGci...",
        "supabase_service_role_key": "sr-key",
        "clinical_note": "Patient complains of chest pain",
        "diagnosis": "Hypertension",
        "notes": "Free text clinical notes",
        "content": "Raw content",
        "appointment_date": "2026-12-01",
    }
    cleaned = sanitize_metadata(raw_meta)
    assert cleaned == {"appointment_date": "2026-12-01"}

    svc = AuditService(world.db, world.settings)
    logged = await svc.log_event(
        action=AuditAction.APPOINTMENT_REQUESTED,
        entity_type=AuditEntityType.APPOINTMENT,
        entity_id="00000000-0000-0000-0000-000000000001",
        hospital_id=world.hospital["h1"]["id"],
        actor_id=world.p1.user_id,
        actor_role=AuditActorRole.PATIENT,
        description="Safe metadata check",
        metadata=raw_meta,
    )
    assert logged is not None
    persisted = (await world.api("GET", f"/admin/audit-logs/{logged['id']}", world.admin)).json()
    assert persisted["metadata"] == {"appointment_date": "2026-12-01"}

    # 3. Failed login threshold (>=5 from same IP) triggers SECURITY_ALERT_TRIGGERED & platform admin notification only
    world.settings.trust_proxy_headers = True
    world.settings.trusted_proxy_ips = ["127.0.0.1/32"]
    for _ in range(5):
        r_fail = await world.api(
            "POST",
            "/auth/login",
            headers={"X-Forwarded-For": "203.0.113.77"},
            json={"email": world.p1.email, "password": "WrongPassword!"},
        )
        assert r_fail.status_code == 401

    sec_r = await world.api("GET", "/admin/security/activity?hours=24", world.admin)
    assert sec_r.status_code == 200, sec_r.text
    sec_body = sec_r.json()
    assert sec_body["summary"]["failed_logins"] >= 5
    assert sec_body["summary"]["security_alerts_triggered"] >= 1
    assert any(a["code"] == "FAILED_LOGIN_THRESHOLD" for a in sec_body["alerts"])
    assert any(s["ip_address"] == "203.0.113.77" and s["count"] >= 5 for s in sec_body["suspicious_sources"])

    # Platform admin receives SECURITY_ALERT; hospital-scoped admin does NOT receive platform alert
    assert len(await world.notifications(world.admin, "SECURITY_ALERT")) >= 1
    assert len(await world.notifications(world.h1_admin, "SECURITY_ALERT")) == 0
