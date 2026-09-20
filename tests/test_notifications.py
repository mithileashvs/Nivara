"""Notifications are created for each appointment lifecycle event."""


async def test_request_notifies_doctor(world):
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 201, r.text

    notes = await world.notifications(world.d1, "APPOINTMENT_REQUESTED")
    assert len(notes) == 1
    assert notes[0]["related_appointment_id"] == r.json()["id"]


async def test_accept_notifies_patient(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    notes = await world.notifications(world.p1, "APPOINTMENT_ACCEPTED")
    assert len(notes) == 1
    assert notes[0]["related_appointment_id"] == appt["id"]


async def test_reject_notifies_patient(world):
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    appt_id = r.json()["id"]
    r = await world.api("POST", f"/appointments/{appt_id}/reject", world.d1, json={"reason": "Unavailable"})
    assert r.status_code == 200, r.text
    notes = await world.notifications(world.p1, "APPOINTMENT_REJECTED")
    assert len(notes) == 1


async def test_cancel_by_patient_notifies_doctor(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    r = await world.api("POST", f"/appointments/{appt['id']}/cancel", world.p1, json={})
    assert r.status_code == 200, r.text
    notes = await world.notifications(world.d1, "APPOINTMENT_CANCELLED")
    assert len(notes) == 1


async def test_cancel_by_doctor_notifies_patient(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    r = await world.api("POST", f"/appointments/{appt['id']}/cancel", world.d1, json={})
    assert r.status_code == 200, r.text
    notes = await world.notifications(world.p1, "APPOINTMENT_CANCELLED")
    assert len(notes) == 1


async def test_reschedule_notifies_the_other_party(world):
    await world.add_window(world.d1)
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    new_slot = await world.slot_at(world.d1, "09:30")
    r = await world.api("POST", f"/appointments/{appt['id']}/reschedule", world.p1, json={"new_slot_id": new_slot["id"]})
    assert r.status_code == 200, r.text
    notes = await world.notifications(world.d1, "APPOINTMENT_RESCHEDULED")
    assert len(notes) == 1


async def test_unread_count_and_mark_read(world):
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 201, r.text

    r = await world.api("GET", "/notifications/unread-count", world.d1)
    assert r.status_code == 200, r.text
    assert r.json()["unread"] == 1

    notes = await world.notifications(world.d1)
    r = await world.api("POST", f"/notifications/{notes[0]['id']}/read", world.d1)
    assert r.status_code == 200, r.text
    assert r.json()["is_read"] is True

    r = await world.api("GET", "/notifications/unread-count", world.d1)
    assert r.json()["unread"] == 0


async def test_mark_all_read(world):
    await world.add_window(world.d1, start="09:00", end="11:00")
    for t in ("09:00", "09:30", "10:00"):
        slot = await world.slot_at(world.d1, t)
        r = await world.request(world.p1, slot["id"])
        assert r.status_code == 201, r.text

    r = await world.api("POST", "/notifications/read-all", world.d1)
    assert r.status_code == 200, r.text
    r = await world.api("GET", "/notifications/unread-count", world.d1)
    assert r.json()["unread"] == 0


async def test_notification_not_found_for_other_user(world):
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    await world.request(world.p1, slot["id"])
    notes = await world.notifications(world.d1)
    # p1 trying to mark d1's notification as read: not owned, so 404.
    r = await world.api("POST", f"/notifications/{notes[0]['id']}/read", world.p1)
    assert r.status_code == 404, r.text
