"""Phase 8 Two-Step Rescheduling & Concurrency Validation Suite."""
from __future__ import annotations

import asyncio


async def test_two_step_reschedule_approve_and_reject_and_cancel_while_pending(world):
    await world.add_window(world.d1, start="09:00", end="12:00")

    # 1. Approve flow: CONFIRMED (09:00) -> RESCHEDULE_REQUESTED -> CONFIRMED (09:30), frees 09:00
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    s_0900 = await world.slot_at(world.d1, "09:00")
    s_0930 = await world.slot_at(world.d1, "09:30")

    r_req = await world.api(
        "POST",
        f"/appointments/{appt['id']}/reschedule",
        world.p1,
        json={"new_slot_id": s_0930["id"], "reason": "Morning traffic"},
    )
    assert r_req.status_code == 200, r_req.text
    assert r_req.json()["status"] == "RESCHEDULE_REQUESTED"
    assert (await world.slot_doc(s_0900["id"]))["status"] == "BOOKED"
    assert (await world.slot_doc(s_0930["id"]))["status"] == "HELD"

    doc_reqs = (await world.api("GET", "/doctors/me/reschedule-requests?status=REQUESTED", world.d1)).json()
    assert doc_reqs["total"] == 1
    req_id = doc_reqs["items"][0]["id"]

    r_app = await world.api("POST", f"/reschedule-requests/{req_id}/approve", world.d1, json={"reason": "Approved"})
    assert r_app.status_code == 200, r_app.text
    assert r_app.json()["status"] == "CONFIRMED"
    assert r_app.json()["start_time"] == "09:30"
    assert (await world.slot_doc(s_0930["id"]))["status"] == "BOOKED"
    assert (await world.slot_doc(s_0900["id"]))["status"] == "AVAILABLE"
    assert len(await world.notifications(world.p1, "RESCHEDULE_APPROVED")) == 1

    # 2. Reject flow: keeps original slot (09:30) CONFIRMED and releases held slot (10:00)
    s_1000 = await world.slot_at(world.d1, "10:00")
    r_req2 = await world.api(
        "POST",
        f"/appointments/{appt['id']}/reschedule",
        world.p1,
        json={"new_slot_id": s_1000["id"], "reason": "Try 10am"},
    )
    assert r_req2.status_code == 200, r_req2.text
    req_id2 = (await world.api("GET", "/doctors/me/reschedule-requests?status=REQUESTED", world.d1)).json()["items"][0]["id"]

    r_rej = await world.api("POST", f"/reschedule-requests/{req_id2}/reject", world.d1, json={"reason": "Surgery at 10am"})
    assert r_rej.status_code == 200, r_rej.text
    assert r_rej.json()["status"] == "CONFIRMED"
    assert r_rej.json()["start_time"] == "09:30"
    assert (await world.slot_doc(s_0930["id"]))["status"] == "BOOKED"
    assert (await world.slot_doc(s_1000["id"]))["status"] == "AVAILABLE"
    assert len(await world.notifications(world.p1, "RESCHEDULE_REJECTED")) == 1

    # 3. Cancel while RESCHEDULE_REQUESTED releases BOTH slots and marks request CANCELLED
    s_1030 = await world.slot_at(world.d1, "10:30")
    r_req3 = await world.api(
        "POST",
        f"/appointments/{appt['id']}/reschedule",
        world.p1,
        json={"new_slot_id": s_1030["id"], "reason": "Try 10:30"},
    )
    assert r_req3.status_code == 200, r_req3.text
    req_id3 = (await world.api("GET", "/doctors/me/reschedule-requests?status=REQUESTED", world.d1)).json()["items"][0]["id"]

    r_cancel = await world.api("POST", f"/appointments/{appt['id']}/cancel", world.p1, json={"reason": "Trip postponed"})
    assert r_cancel.status_code == 200, r_cancel.text
    assert r_cancel.json()["status"] == "CANCELLED"
    assert (await world.slot_doc(s_0930["id"]))["status"] == "AVAILABLE"
    assert (await world.slot_doc(s_1030["id"]))["status"] == "AVAILABLE"
    req_doc = (await world.api("GET", f"/reschedule-requests/{req_id3}", world.p1)).json()
    assert req_doc["status"] == "CANCELLED"


async def test_reschedule_overlap_guards_on_approve_and_doctor_direct_reschedule(world):
    await world.add_window(world.d1, hospital="h1", dept="h1_general", start="09:00", end="11:00")
    await world.add_window(world.d3, hospital="h2", dept="h2_general", start="09:00", end="11:00")

    # P1 has confirmed d1@09:00; requests reschedule to d1@09:30 (still active at 09:00)
    appt1 = await world.book(world.p1, world.d1, "09:00", confirm=True)
    s_d1_0930 = await world.slot_at(world.d1, "09:30")
    r_req = await world.api(
        "POST",
        f"/appointments/{appt1['id']}/reschedule",
        world.p1,
        json={"new_slot_id": s_d1_0930["id"], "reason": "Move to 09:30"},
    )
    assert r_req.status_code == 200, r_req.text
    req_id = (await world.api("GET", "/doctors/me/reschedule-requests?status=REQUESTED", world.d1)).json()["items"][0]["id"]

    # P1 subsequently books d3@09:30 (valid now because appt1 occupies 09:00)
    appt2 = await world.book(world.p1, world.d3, "09:30", confirm=True)
    assert appt2["start_time"] == "09:30"

    # Approving appt1 -> 09:30 MUST fail 409 patient_time_conflict
    r_app = await world.api("POST", f"/reschedule-requests/{req_id}/approve", world.d1, json={})
    assert r_app.status_code == 409, r_app.text
    assert r_app.json()["error"]["code"] == "patient_time_conflict"

    # Doctor direct reschedule into another overlapping confirmed booking of the same patient MUST fail 409
    appt3 = await world.book(world.p2, world.d1, "10:00", confirm=True)
    await world.book(world.p2, world.d3, "10:30", confirm=True)
    s_d1_1030 = await world.slot_at(world.d1, "10:30")
    r_dir = await world.api(
        "POST",
        f"/appointments/{appt3['id']}/reschedule",
        world.d1,
        json={"new_slot_id": s_d1_1030["id"], "reason": "Doctor shift"},
    )
    assert r_dir.status_code == 409, r_dir.text
    assert r_dir.json()["error"]["code"] == "patient_time_conflict"


async def test_concurrent_reschedule_requests_and_decisions_and_offer_accept(world):
    await world.add_window(world.d1, start="09:00", end="11:30")
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    s_0930 = await world.slot_at(world.d1, "09:30")
    s_1000 = await world.slot_at(world.d1, "10:00")

    # 1. Concurrent patient reschedule requests on the same CONFIRMED appointment
    res_reqs = await asyncio.gather(
        world.api(
            "POST",
            f"/appointments/{appt['id']}/reschedule",
            world.p1,
            json={"new_slot_id": s_0930["id"], "reason": "Race 1"},
        ),
        world.api(
            "POST",
            f"/appointments/{appt['id']}/reschedule",
            world.p1,
            json={"new_slot_id": s_1000["id"], "reason": "Race 2"},
        ),
        return_exceptions=True,
    )
    codes_req = sorted(r.status_code for r in res_reqs if not isinstance(r, Exception))
    assert codes_req == [200, 409], f"Expected [200, 409], got {codes_req}"
    pending_count = await world.db["rescheduling_requests"].count_documents(
        {"appointment_id": appt["id"], "status": "REQUESTED"}
    )
    assert pending_count == 1

    # 2. Concurrent approve vs reject on that single pending request -> [200, 409]
    req_id = (await world.api("GET", "/doctors/me/reschedule-requests?status=REQUESTED", world.d1)).json()["items"][0]["id"]
    res_dec = await asyncio.gather(
        world.api("POST", f"/reschedule-requests/{req_id}/approve", world.d1, json={}),
        world.api("POST", f"/reschedule-requests/{req_id}/reject", world.d1, json={}),
        return_exceptions=True,
    )
    codes_dec = sorted(r.status_code for r in res_dec if not isinstance(r, Exception))
    assert codes_dec == [200, 409], f"Expected [200, 409], got {codes_dec}"

    # 3. Concurrent accept_offer race for a single waitlist offer -> exactly one 200, one 409
    appt_p2 = await world.book(world.p2, world.d1, "10:30", confirm=True)
    wl_r = await world.api(
        "POST",
        "/waitlist",
        world.p3,
        json={"doctor_id": world.d1.id, "date_from": world.tomorrow.isoformat(), "date_to": world.tomorrow.isoformat()},
    )
    assert wl_r.status_code == 201, wl_r.text
    c_r = await world.api("POST", f"/appointments/{appt_p2['id']}/cancel", world.p2, json={"reason": "Cancel"})
    assert c_r.status_code == 200, c_r.text

    offers = (await world.api("GET", "/waitlist/offers", world.p3)).json()
    assert len(offers) == 1
    offer_id = offers[0]["id"]
    res_acc = await asyncio.gather(
        world.api("POST", f"/waitlist/offers/{offer_id}/accept", world.p3, json={"reason": "Take it"}),
        world.api("POST", f"/waitlist/offers/{offer_id}/accept", world.p3, json={"reason": "Take it 2"}),
        return_exceptions=True,
    )
    codes_acc = sorted(r.status_code for r in res_acc if not isinstance(r, Exception))
    assert codes_acc == [200, 409], f"Expected [200, 409], got {codes_acc}"
