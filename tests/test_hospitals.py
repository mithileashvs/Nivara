"""Hospital creation, retrieval, department association, and intake open/closed."""


async def test_create_hospital(world):
    r = await world.api("POST", "/hospitals", world.admin, json={
        "name": "Test General Hospital", "address": "42 Test Ave",
        "location": {"city": "Madurai", "latitude": 9.9252, "longitude": 78.1198},
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Test General Hospital"
    assert body["appointment_intake_status"] == "OPEN"


async def test_get_hospital_with_departments(world):
    r = await world.api("GET", f"/hospitals/{world.hospital['h1']['id']}", world.p1)
    assert r.status_code == 200, r.text
    body = r.json()
    names = {d["name"] for d in body["departments"]}
    assert {"General Medicine", "Cardiology", "Dermatology"} <= names


async def test_list_hospitals(world):
    r = await world.api("GET", "/hospitals", world.p1)
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 2


async def test_hospital_intake_open_by_default(world):
    r = await world.api("GET", f"/hospitals/{world.hospital['h1']['id']}/availability", world.p1)
    assert r.status_code == 200, r.text
    assert r.json()["appointment_intake_status"] == "OPEN"


async def test_hospital_intake_close_and_reopen(world):
    r = await world.api("PUT", f"/hospitals/{world.hospital['h1']['id']}/intake", world.admin, json={"status": "CLOSED", "reason": "Maintenance"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["previous_status"] == "OPEN"
    assert body["appointment_intake_status"] == "CLOSED"

    r = await world.api("GET", f"/hospitals/{world.hospital['h1']['id']}/availability", world.p1)
    assert r.json()["appointment_intake_status"] == "CLOSED"
    assert r.json()["accepting_new_requests"] is False

    r = await world.api("PUT", f"/hospitals/{world.hospital['h1']['id']}/intake", world.admin, json={"status": "OPEN"})
    assert r.status_code == 200, r.text
    assert r.json()["appointment_intake_status"] == "OPEN"


async def test_availability_reports_real_slot_counts_not_a_load_score(world):
    """The API must report actual bookable-slot facts, never an invented 'load' percentage."""
    await world.add_window(world.d1)
    r = await world.api("GET", f"/hospitals/{world.hospital['h1']['id']}/availability", world.p1)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["total_bookable_slots"], int)
    assert "load" not in body  # no fabricated capacity metric anywhere in the response
    dept = next(d for d in body["departments"] if d["name"] == "General Medicine")
    assert dept["bookable_slots"] == 6  # 09:00-12:00 in 30-minute slots
