"""Phase 8 Smart Waitlist, Slot Offers, Queue Progression, Overlap & Expiration Suite."""
from __future__ import annotations

from datetime import timedelta

from app.services.maintenance_service import MaintenanceService
from app.utils.time_utils import utcnow


async def test_waitlist_validation_and_dynamic_queue_positions(world):
    yesterday = (world.tomorrow - timedelta(days=2)).isoformat()
    r_past = await world.api(
        "POST",
        "/waitlist",
        world.p1,
        json={"doctor_id": world.d1.id, "date_from": yesterday, "date_to": yesterday},
    )
    assert r_past.status_code == 400
    assert r_past.json()["error"]["code"] == "date_in_past"

    # Doctor d1 belongs to h1, not h2 -> incompatible_hospital
    r_incompat = await world.api(
        "POST",
        "/waitlist",
        world.p1,
        json={
            "doctor_id": world.d1.id,
            "hospital_id": world.hospital["h2"]["id"],
            "date_from": world.tomorrow.isoformat(),
            "date_to": world.tomorrow.isoformat(),
        },
    )
    assert r_incompat.status_code == 400
    assert r_incompat.json()["error"]["code"] == "incompatible_hospital"

    payload = {"doctor_id": world.d1.id, "date_from": world.tomorrow.isoformat(), "date_to": world.tomorrow.isoformat()}
    w1 = await world.api("POST", "/waitlist", world.p1, json=payload)
    assert w1.status_code == 201, w1.text
    assert w1.json()["queue_position"] == 1 and w1.json()["patients_ahead"] == 0

    # Duplicate active entry -> 409
    w1_dup = await world.api("POST", "/waitlist", world.p1, json=payload)
    assert w1_dup.status_code == 409
    assert w1_dup.json()["error"]["code"] == "duplicate_waitlist_entry"

    w2 = await world.api("POST", "/waitlist", world.p2, json=payload)
    assert w2.status_code == 201, w2.text
    assert w2.json()["queue_position"] == 2 and w2.json()["patients_ahead"] == 1

    # Doctor waitlist view & stats
    d_stats = (await world.api("GET", "/doctors/me/waitlist/statistics", world.d1)).json()
    assert d_stats["active_waitlist_patients"] == 2
    d_list = (await world.api("GET", "/doctors/me/waitlist", world.d1)).json()
    assert d_list["total"] == 2


async def test_waitlist_offer_decline_progression_and_accept_with_real_patient_data(world):
    await world.add_window(world.d1, start="09:00", end="10:00")
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)

    # P2 joins first, then P3
    w_p2 = await world.api(
        "POST",
        "/waitlist",
        world.p2,
        json={"doctor_id": world.d1.id, "date_from": world.tomorrow.isoformat(), "date_to": world.tomorrow.isoformat()},
    )
    assert w_p2.status_code == 201, w_p2.text
    w_p3 = await world.api(
        "POST",
        "/waitlist",
        world.p3,
        json={"doctor_id": world.d1.id, "date_from": world.tomorrow.isoformat(), "date_to": world.tomorrow.isoformat()},
    )
    assert w_p3.status_code == 201, w_p3.text

    # Cancel appt -> automatic offer reserved (HELD) for P2
    c_r = await world.api("POST", f"/appointments/{appt['id']}/cancel", world.p1, json={"reason": "Busy"})
    assert c_r.status_code == 200, c_r.text

    s_0900 = await world.slot_doc(appt["slot_id"])
    assert s_0900["status"] == "HELD"
    assert s_0900["waitlist_offer_id"] is not None

    offers_p2 = (await world.api("GET", "/waitlist/offers", world.p2)).json()
    assert len(offers_p2) == 1 and offers_p2[0]["status"] == "PENDING"
    assert len(await world.notifications(world.p2, "WAITLIST_OFFER_AVAILABLE")) == 1

    # P2 declines -> triggers automatic progression to P3
    dec = await world.api("POST", f"/waitlist/offers/{offers_p2[0]['id']}/decline", world.p2, json={"reason": "No longer needed"})
    assert dec.status_code == 200, dec.text
    assert dec.json()["status"] == "DECLINED"
    assert len(await world.notifications(world.p2, "WAITLIST_OFFER_DECLINED")) == 1

    offers_p3 = (await world.api("GET", "/waitlist/offers?status=PENDING", world.p3)).json()
    assert len(offers_p3) == 1

    # P3 accepts -> formal REQUESTED appointment preserving doctor approval + real patient_name + valid consultation_type
    acc = await world.api("POST", f"/waitlist/offers/{offers_p3[0]['id']}/accept", world.p3, json={"reason": "I can make 9am"})
    assert acc.status_code == 200, acc.text
    body = acc.json()
    assert body["offer"]["status"] == "ACCEPTED"
    assert body["appointment"]["status"] == "REQUESTED"
    assert body["appointment"]["patient_name"] == world.p3.name
    assert body["appointment"]["consultation_type"] in ("FIRST_VISIT", "FOLLOW_UP", "ROUTINE_CHECKUP")
    assert len(await world.notifications(world.p3, "WAITLIST_OFFER_ACCEPTED")) == 1

    # Doctor accepts the waitlist-created appointment -> CONFIRMED
    d_acc = await world.api("POST", f"/appointments/{body['appointment']['id']}/accept", world.d1, json={})
    assert d_acc.status_code == 200 and d_acc.json()["status"] == "CONFIRMED"


async def test_waitlist_offer_accept_overlap_and_offer_expiry_recovery(world):
    await world.add_window(world.d1, hospital="h1", dept="h1_general", start="09:00", end="10:00")
    await world.add_window(world.d3, hospital="h2", dept="h2_general", start="09:00", end="10:00")

    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    await world.api(
        "POST",
        "/waitlist",
        world.p2,
        json={"doctor_id": world.d1.id, "date_from": world.tomorrow.isoformat(), "date_to": world.tomorrow.isoformat()},
    )
    await world.api(
        "POST",
        "/waitlist",
        world.p3,
        json={"doctor_id": world.d1.id, "date_from": world.tomorrow.isoformat(), "date_to": world.tomorrow.isoformat()},
    )

    # P1 cancels d1@09:00 -> automatic held offer created for P2
    await world.api("POST", f"/appointments/{appt['id']}/cancel", world.p1, json={"reason": "Cancel"})

    p2_offer = (await world.api("GET", "/waitlist/offers?status=PENDING", world.p2)).json()[0]

    # P2 then books d3 at 09:00 before accepting the d1@09:00 offer -> overlap guard rejects accept
    await world.book(world.p2, world.d3, "09:00", confirm=True)
    acc_conflict = await world.api("POST", f"/waitlist/offers/{p2_offer['id']}/accept", world.p2, json={})
    assert acc_conflict.status_code == 409, acc_conflict.text
    assert acc_conflict.json()["error"]["code"] == "patient_time_conflict"

    # Expire p2_offer's hold & expires_at -> MaintenanceService.run_all() expires offer & offers to P3
    past = utcnow() - timedelta(minutes=30)
    await world.db["waitlist_offers"].update_one({"_id": p2_offer["id"]}, {"$set": {"expires_at": past}})
    await world.db["appointment_slots"].update_one({"_id": appt["slot_id"]}, {"$set": {"held_until": past}})

    maint = await MaintenanceService(world.db, world.settings).run_all()
    assert maint["expired_holds"] >= 1 or maint["waitlist_offers_expired"] >= 1
    assert (await world.db["waitlist_offers"].find_one({"_id": p2_offer["id"]}))["status"] == "EXPIRED"

    p3_offers = (await world.api("GET", "/waitlist/offers?status=PENDING", world.p3)).json()
    assert len(p3_offers) == 1


async def test_waitlist_history_sql_pagination(world):
    # Create 3 waitlist entries on distinct date ranges, cancel all 3, verify multi-page /waitlist/history
    entry_ids = []
    for offset in (1, 2, 3):
        d = (world.tomorrow + timedelta(days=offset)).isoformat()
        r = await world.api(
            "POST",
            "/waitlist",
            world.p1,
            json={"doctor_id": world.d1.id, "date_from": d, "date_to": d},
        )
        assert r.status_code == 201, r.text
        entry_ids.append(r.json()["id"])

    for eid in entry_ids:
        del_r = await world.api("DELETE", f"/waitlist/{eid}", world.p1)
        assert del_r.status_code == 200, del_r.text

    p1 = (await world.api("GET", "/waitlist/history?page=1&page_size=2", world.p1)).json()
    p2 = (await world.api("GET", "/waitlist/history?page=2&page_size=2", world.p1)).json()
    assert p1["total"] == 3 and len(p1["items"]) == 2
    assert p2["total"] == 3 and len(p2["items"]) == 1
    assert {i["id"] for i in p1["items"]}.isdisjoint({i["id"] for i in p2["items"]})
