"""Read-only admin appointment monitoring: GET /admin/appointments.

Admins may view, filter and paginate appointments for platform monitoring, but they never
approve, reject, complete or mark an appointment no-show — the doctor remains the sole
decision-maker. See tests/test_rbac.py for the accept/reject role checks.
"""


async def test_admin_can_retrieve_appointments(world):
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 201, r.text

    r = await world.api("GET", "/admin/appointments", world.admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    item = next(i for i in body["items"] if i["id"] == r.json()["items"][0]["id"])
    # Only platform-monitoring fields are exposed — no clinical "reason" text.
    assert "reason" not in item
    for field in (
        "id", "patient_id", "patient_name", "doctor_id", "doctor_name", "hospital_id",
        "department_id", "appointment_date", "start_time", "end_time", "consultation_type",
        "status", "created_at",
    ):
        assert field in item


async def test_admin_can_filter_by_status(world):
    await world.add_window(world.d1)
    await world.book(world.p1, world.d1, "09:00", confirm=True)
    await world.book(world.p2, world.d1, "09:30", confirm=False)

    r = await world.api("GET", "/admin/appointments?status=CONFIRMED", world.admin)
    assert r.status_code == 200, r.text
    assert r.json()["items"], r.text
    assert all(a["status"] == "CONFIRMED" for a in r.json()["items"])

    r = await world.api("GET", "/admin/appointments?status=REQUESTED", world.admin)
    assert r.status_code == 200, r.text
    assert all(a["status"] == "REQUESTED" for a in r.json()["items"])


async def test_admin_can_filter_by_doctor(world):
    await world.add_window(world.d1)
    await world.add_window(world.d2, dept="h1_dermatology")
    appt1 = await world.book(world.p1, world.d1, "09:00")
    await world.book(world.p2, world.d2, "09:00")

    r = await world.api("GET", f"/admin/appointments?doctor_id={world.d1.id}", world.admin)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items and all(a["doctor_id"] == world.d1.id for a in items)
    assert any(a["id"] == appt1["id"] for a in items)


async def test_admin_can_filter_by_patient(world):
    await world.add_window(world.d1)
    appt1 = await world.book(world.p1, world.d1, "09:00")
    await world.book(world.p2, world.d1, "09:30")

    r = await world.api("GET", f"/admin/appointments?patient_id={world.p1.id}", world.admin)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items and all(a["patient_id"] == world.p1.id for a in items)
    assert any(a["id"] == appt1["id"] for a in items)


async def test_admin_can_filter_by_hospital(world):
    await world.add_window(world.d1)  # h1
    await world.add_window(world.d3, hospital="h2", dept="h2_general")  # h2
    appt1 = await world.book(world.p1, world.d1, "09:00")
    await world.book(world.p2, world.d3, "09:00")

    r = await world.api("GET", f"/admin/appointments?hospital_id={world.hospital['h1']['id']}", world.admin)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items and all(a["hospital_id"] == world.hospital["h1"]["id"] for a in items)
    assert any(a["id"] == appt1["id"] for a in items)


async def test_admin_can_filter_by_department(world):
    await world.add_window(world.d1, dept="h1_general")
    await world.add_window(world.d2, dept="h1_dermatology")
    appt1 = await world.book(world.p1, world.d1, "09:00")
    await world.book(world.p2, world.d2, "09:00")

    r = await world.api("GET", f"/admin/appointments?department_id={world.dept['h1_general']['id']}", world.admin)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items and all(a["department_id"] == world.dept["h1_general"]["id"] for a in items)
    assert any(a["id"] == appt1["id"] for a in items)


async def test_admin_can_filter_by_date(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00")
    the_date = appt["appointment_date"]

    r = await world.api("GET", f"/admin/appointments?appointment_date={the_date}", world.admin)
    assert r.status_code == 200, r.text
    assert any(a["id"] == appt["id"] for a in r.json()["items"])

    r = await world.api("GET", f"/admin/appointments?date_from={the_date}&date_to={the_date}", world.admin)
    assert r.status_code == 200, r.text
    assert any(a["id"] == appt["id"] for a in r.json()["items"])

    r = await world.api("GET", "/admin/appointments?date_from=2099-01-01", world.admin)
    assert r.status_code == 200, r.text
    assert not any(a["id"] == appt["id"] for a in r.json()["items"])


async def test_admin_appointments_pagination(world):
    await world.add_window(world.d1, start="09:00", end="12:00", duration=30)
    for t in ("09:00", "09:30", "10:00"):
        await world.book(world.p1 if t != "10:00" else world.p2, world.d1, t)

    r = await world.api("GET", "/admin/appointments?page=1&page_size=2", world.admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 3

    r2 = await world.api("GET", "/admin/appointments?page=2&page_size=2", world.admin)
    assert r2.status_code == 200, r2.text
    ids_p1 = {a["id"] for a in body["items"]}
    ids_p2 = {a["id"] for a in r2.json()["items"]}
    assert ids_p1.isdisjoint(ids_p2)


async def test_patient_cannot_access_admin_appointment_endpoint(world):
    r = await world.api("GET", "/admin/appointments", world.p1)
    assert r.status_code == 403, r.text


async def test_doctor_cannot_access_admin_appointment_endpoint(world):
    r = await world.api("GET", "/admin/appointments", world.d1)
    assert r.status_code == 403, r.text


async def test_admin_cannot_approve_appointment_via_any_route(world):
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 201, r.text
    appt_id = r.json()["id"]

    r = await world.api("POST", f"/appointments/{appt_id}/accept", world.admin, json={})
    assert r.status_code == 403, r.text
    # No admin-scoped decision route exists at all.
    r = await world.api("POST", f"/admin/appointments/{appt_id}/accept", world.admin, json={})
    assert r.status_code == 404, r.text


async def test_admin_cannot_reject_appointment_via_any_route(world):
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 201, r.text
    appt_id = r.json()["id"]

    r = await world.api("POST", f"/appointments/{appt_id}/reject", world.admin, json={})
    assert r.status_code == 403, r.text
    r = await world.api("POST", f"/admin/appointments/{appt_id}/reject", world.admin, json={})
    assert r.status_code == 404, r.text


async def test_hospital_scoped_admin_sees_only_own_hospital(world):
    await world.add_window(world.d1)  # h1
    await world.add_window(world.d3, hospital="h2", dept="h2_general")  # h2
    appt_h1 = await world.book(world.p1, world.d1, "09:00")
    await world.book(world.p2, world.d3, "09:00")

    r = await world.api("GET", "/admin/appointments", world.h1_admin)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert all(a["hospital_id"] == world.hospital["h1"]["id"] for a in items)
    assert any(a["id"] == appt_h1["id"] for a in items)


async def test_hospital_scoped_admin_cannot_filter_by_other_hospital(world):
    r = await world.api("GET", f"/admin/appointments?hospital_id={world.hospital['h2']['id']}", world.h1_admin)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "hospital_scope_forbidden"


async def test_existing_appointment_privacy_rules_remain_intact(world):
    """Patients/doctors still only see their own appointments via the participant endpoint;
    the new admin endpoint doesn't change that."""
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 201, r.text
    appt_id = r.json()["id"]

    r = await world.api("GET", f"/appointments/{appt_id}", world.p2)
    assert r.status_code == 404, r.text  # not this patient's appointment -> 404, not 403

    r = await world.api("GET", f"/appointments/{appt_id}", world.p1)
    assert r.status_code == 200, r.text
