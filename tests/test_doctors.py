"""Doctor profile, search/filtering, availability, slot generation, and statistics."""


async def test_get_my_doctor_profile(world):
    r = await world.api("GET", "/doctors/me", world.d1)
    assert r.status_code == 200, r.text
    assert r.json()["specialty"] == "General Medicine"
    assert r.json()["profile_status"] == "ACTIVE"


async def test_update_my_doctor_profile(world):
    r = await world.api("PATCH", "/doctors/me", world.d1, json={"consultation_fee": 350})
    assert r.status_code == 200, r.text
    assert r.json()["consultation_fee"] == 350


async def test_search_by_specialty(world):
    r = await world.api("GET", "/doctors?specialty=Dermatology", world.p1)
    assert r.status_code == 200, r.text
    names = {d["name"] for d in r.json()["items"]}
    assert world.d2.name in names
    assert world.d1.name not in names


async def test_search_by_hospital(world):
    r = await world.api("GET", f"/doctors?hospital_id={world.hospital['h2']['id']}", world.p1)
    assert r.status_code == 200, r.text
    names = {d["name"] for d in r.json()["items"]}
    assert world.d3.name in names
    assert world.d1.name not in names


async def test_search_only_active_doctors_visible(world):
    # d1/d2/d3 are all ACTIVE in the World scenario; a still-PENDING doctor must not appear.
    pending = await world.register_doctor("Dr. Pending", "pending@smartcare-demo.com", "General Medicine")
    r = await world.api("GET", "/doctors?specialty=General Medicine", world.p1)
    names = {d["name"] for d in r.json()["items"]}
    assert pending.name not in names


async def test_get_public_doctor_profile(world):
    r = await world.api("GET", f"/doctors/{world.d1.id}", world.p1)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == world.d1.name


async def test_add_availability_generates_slots(world):
    r = await world.add_window(world.d1, start="09:00", end="10:00", duration=30)
    assert r.status_code == 201, r.text
    assert r.json()["slots_created"] == 2


async def test_list_availability(world):
    await world.add_window(world.d1)
    r = await world.api("GET", "/doctors/me/availability", world.d1)
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 1


async def test_delete_availability_removes_unreserved_slots(world):
    r = await world.add_window(world.d1, start="09:00", end="10:00", duration=30)
    window_id = r.json()["id"]
    r = await world.api("DELETE", f"/doctors/me/availability/{window_id}", world.d1)
    assert r.status_code == 200, r.text
    slots = await world.slots(world.d1)
    assert slots == []


async def test_delete_availability_blocked_if_appointment_exists(world):
    r = await world.add_window(world.d1, start="09:00", end="10:00", duration=30)
    window_id = r.json()["id"]
    slot = await world.slot_at(world.d1, "09:00")
    req = await world.request(world.p1, slot["id"])
    assert req.status_code == 201, req.text
    r = await world.api("DELETE", f"/doctors/me/availability/{window_id}", world.d1)
    assert r.status_code == 409, r.text


async def test_doctor_intake_close_blocks_new_requests(world):
    await world.add_window(world.d1)
    r = await world.api("PUT", f"/doctors/{world.d1.id}/intake-status", world.d1, json={"availability_status": "CLOSED"})
    assert r.status_code == 200, r.text
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "doctor_intake_closed"


async def test_doctor_statistics_reflects_real_counts(world):
    await world.add_window(world.d1)
    appt1 = await world.book(world.p1, world.d1, "09:00", confirm=True)
    slot2 = await world.slot_at(world.d1, "09:30")
    req = await world.request(world.p2, slot2["id"])
    assert req.status_code == 201, req.text

    r = await world.api("GET", "/doctors/me/statistics", world.d1)
    assert r.status_code == 200, r.text
    stats = r.json()
    assert stats["confirmed_appointments"] == 1
    assert stats["pending_requests"] == 1
    assert stats["completed_appointments"] == 0
    assert stats["total_patients"] == 2


async def test_doctor_statistics_requires_doctor_role(world):
    r = await world.api("GET", "/doctors/me/statistics", world.p1)
    assert r.status_code == 403, r.text
