"""Role-based access control: each role is confined to what it should be able to do."""


async def test_patient_cannot_access_doctor_only_endpoint(world):
    r = await world.api("GET", "/doctors/me", world.p1)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "forbidden_role"


async def test_patient_cannot_access_admin_endpoint(world):
    r = await world.api("GET", "/admin/users", world.p1)
    assert r.status_code == 403, r.text


async def test_doctor_cannot_access_admin_only_endpoint(world):
    r = await world.api("GET", "/admin/users", world.d1)
    assert r.status_code == 403, r.text


async def test_doctor_cannot_access_admin_statistics(world):
    r = await world.api("GET", "/admin/statistics", world.d1)
    assert r.status_code == 403, r.text


async def test_doctor_cannot_modify_another_doctors_availability(world):
    # d2 tries to delete a window that belongs to d1.
    r = await world.add_window(world.d1)
    assert r.status_code == 201, r.text
    windows = await world.api("GET", "/doctors/me/availability", world.d1)
    window_id = windows.json()["items"][0]["id"]
    r = await world.api("DELETE", f"/doctors/me/availability/{window_id}", world.d2)
    # d2 has no availability window with this id in their own scope -> not found, never leaks d1's data
    assert r.status_code == 404, r.text


async def test_patient_cannot_approve_appointments(world):
    appt = await world.book(world.p1, world.d1, "09:00", confirm=False) if False else None
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 201, r.text
    appt_id = r.json()["id"]
    # There is no patient-facing accept endpoint at all; the doctor-only route rejects the patient.
    r = await world.api("POST", f"/appointments/{appt_id}/accept", world.p1, json={})
    assert r.status_code == 403, r.text


async def test_admin_cannot_approve_individual_appointments(world):
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 201, r.text
    appt_id = r.json()["id"]
    r = await world.api("POST", f"/appointments/{appt_id}/accept", world.admin, json={})
    assert r.status_code == 403, r.text  # admins are not doctors, so this is doctor-only role check


async def test_admin_cannot_list_appointments_as_participant(world):
    r = await world.api("GET", "/appointments", world.admin)
    assert r.status_code == 403, r.text  # admins have no participant role (patient/doctor)


async def test_hospital_scoped_admin_cannot_manage_other_hospital(world):
    r = await world.api("PATCH", f"/hospitals/{world.hospital['h2']['id']}", world.h1_admin, json={"name": "Renamed"})
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "hospital_scope_forbidden"


async def test_hospital_scoped_admin_can_manage_own_hospital(world):
    r = await world.api("PATCH", f"/hospitals/{world.hospital['h1']['id']}", world.h1_admin, json={"name": "City Care Hospital Renamed"})
    assert r.status_code == 200, r.text


async def test_only_platform_admin_can_create_hospital(world):
    r = await world.api("POST", "/hospitals", world.h1_admin, json={
        "name": "Unauthorized Hospital", "address": "1 Test Road", "location": {"city": "X", "latitude": 1.0, "longitude": 1.0},
    })
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "platform_admin_required"
