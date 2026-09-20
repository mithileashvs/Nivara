"""Hospital, department and doctor intake closure: new requests blocked, existing appointments unchanged."""


async def test_hospital_closure_blocks_new_blocks_existing_unaffected(world):
    await world.add_window(world.d1)
    existing = await world.book(world.p1, world.d1, "09:00", confirm=True)

    r = await world.api("PUT", f"/hospitals/{world.hospital['h1']['id']}/intake", world.admin, json={"status": "CLOSED"})
    assert r.status_code == 200, r.text
    assert r.json()["active_appointments_unaffected"] == 1

    slot = await world.slot_at(world.d1, "09:30")
    r = await world.request(world.p2, slot["id"])
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "hospital_intake_closed"

    # Existing confirmed appointment is untouched.
    r = await world.api("GET", f"/appointments/{existing['id']}", world.p1)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CONFIRMED"


async def test_department_closure_blocks_new_blocks_existing_unaffected(world):
    await world.add_window(world.d1)
    existing = await world.book(world.p1, world.d1, "09:00", confirm=True)

    r = await world.api("PUT", f"/departments/{world.dept['h1_general']['id']}/intake", world.admin, json={"status": "CLOSED"})
    assert r.status_code == 200, r.text
    assert r.json()["active_appointments_unaffected"] == 1

    slot = await world.slot_at(world.d1, "09:30")
    r = await world.request(world.p2, slot["id"])
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "department_intake_closed"

    r = await world.api("GET", f"/appointments/{existing['id']}", world.p1)
    assert r.json()["status"] == "CONFIRMED"


async def test_doctor_closure_blocks_new_blocks_existing_unaffected(world):
    await world.add_window(world.d1)
    existing = await world.book(world.p1, world.d1, "09:00", confirm=True)

    r = await world.api("PUT", f"/doctors/{world.d1.id}/intake-status", world.d1, json={"availability_status": "CLOSED"})
    assert r.status_code == 200, r.text

    slot = await world.slot_at(world.d1, "09:30")
    r = await world.request(world.p2, slot["id"])
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "doctor_intake_closed"

    r = await world.api("GET", f"/appointments/{existing['id']}", world.p1)
    assert r.json()["status"] == "CONFIRMED"


async def test_hospital_closed_reflected_in_search_availability(world):
    await world.add_window(world.d1)
    r = await world.api("PUT", f"/hospitals/{world.hospital['h1']['id']}/intake", world.admin, json={"status": "CLOSED"})
    assert r.status_code == 200, r.text
    r = await world.api("GET", f"/hospitals/{world.hospital['h1']['id']}/availability", world.p1)
    body = r.json()
    assert body["accepting_new_requests"] is False
    assert body["total_bookable_slots"] == 0
    for dept in body["departments"]:
        assert dept["accepting_new_requests"] is False
