"""Full appointment lifecycle, conflict handling, and reschedule behaviour."""


async def test_full_lifecycle_request_to_completed(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    assert appt["status"] == "CONFIRMED"

    await world.make_started(appt["id"])
    r = await world.api("POST", f"/appointments/{appt['id']}/complete", world.d1, json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETED"


async def test_requested_to_rejected(world):
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 201, r.text
    appt_id = r.json()["id"]

    r = await world.api("POST", f"/appointments/{appt_id}/reject", world.d1, json={"reason": "Not available"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REJECTED"

    # Rejecting again is not allowed.
    r = await world.api("POST", f"/appointments/{appt_id}/reject", world.d1, json={})
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "invalid_status_transition"

    # Slot is freed and bookable again.
    slot_doc = await world.slot_doc(slot["id"])
    assert slot_doc["status"] == "AVAILABLE"


async def test_confirmed_to_cancelled(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    r = await world.api("POST", f"/appointments/{appt['id']}/cancel", world.p1, json={"reason": "Change of plans"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CANCELLED"


async def test_confirmed_to_no_show(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    await world.make_started(appt["id"])
    r = await world.api("POST", f"/appointments/{appt['id']}/no-show", world.d1, json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "NO_SHOW"


async def test_cannot_complete_before_start(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    r = await world.api("POST", f"/appointments/{appt['id']}/complete", world.d1, json={})
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "appointment_not_started"


async def test_cannot_cancel_after_started(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    await world.make_started(appt["id"])
    r = await world.api("POST", f"/appointments/{appt['id']}/cancel", world.p1, json={})
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "appointment_started"


async def test_conflict_two_patients_same_slot(world):
    """Patient A requests a slot; patient B's request for the exact same slot must fail with 409."""
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")

    r1 = await world.request(world.p1, slot["id"])
    assert r1.status_code == 201, r1.text

    r2 = await world.request(world.p2, slot["id"])
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] in ("slot_unavailable", "slot_not_available", "slot_held")


async def test_patient_cannot_double_book_overlapping_time(world):
    await world.add_window(world.d1)
    await world.add_window(world.d3, hospital="h2", dept="h2_general")
    slot1 = await world.slot_at(world.d1, "09:00")
    r1 = await world.request(world.p1, slot1["id"])
    assert r1.status_code == 201, r1.text

    slot2 = await world.slot_at(world.d3, "09:00")
    r2 = await world.request(world.p1, slot2["id"])
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "patient_time_conflict"


async def test_patient_pending_request_limit(world):
    await world.add_window(world.d1, start="09:00", end="17:00")
    slots = await world.slots(world.d1)
    limit = world.settings.max_pending_requests_per_patient
    for slot in slots[:limit]:
        r = await world.request(world.p1, slot["id"])
        assert r.status_code == 201, r.text
    r = await world.request(world.p1, slots[limit]["id"])
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "too_many_pending_requests"


async def test_reschedule_by_patient_returns_to_requested(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    new_slot = await world.slot_at(world.d1, "09:30")
    r = await world.api("POST", f"/appointments/{appt['id']}/reschedule", world.p1, json={"new_slot_id": new_slot["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REQUESTED"


async def test_reschedule_by_doctor_stays_confirmed(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    new_slot = await world.slot_at(world.d1, "10:00")
    r = await world.api("POST", f"/appointments/{appt['id']}/reschedule", world.d1, json={"new_slot_id": new_slot["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CONFIRMED"


async def test_history_records_transitions(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    r = await world.api("GET", f"/appointments/{appt['id']}/history", world.p1)
    assert r.status_code == 200, r.text
    statuses = [h["new_status"] for h in r.json()]
    assert statuses == ["REQUESTED", "CONFIRMED"]


async def test_other_patient_cannot_see_appointment(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    r = await world.api("GET", f"/appointments/{appt['id']}", world.p2)
    assert r.status_code == 404, r.text  # not 403 — existence is not revealed either


async def test_appointment_not_found_uses_valid_object_id_shape(world):
    fake_id = "6ab0ce6703a2b6aff2b977df"
    r = await world.api("GET", f"/appointments/{fake_id}", world.p1)
    assert r.status_code == 404, r.text
