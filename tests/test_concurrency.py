"""Concurrency: two patients racing for the same slot must not both succeed.

This drives real concurrent requests (asyncio.gather over the same ASGI app instance) rather than
two sequential calls, exercising the atomic conditional Mongo update in SlotService.claim.
"""
import asyncio


async def test_concurrent_requests_for_same_slot_only_one_wins(world):
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")

    results = await asyncio.gather(
        world.request(world.p1, slot["id"]),
        world.request(world.p2, slot["id"]),
        world.request(world.p3, slot["id"]),
        return_exceptions=True,
    )

    statuses = [r.status_code for r in results if not isinstance(r, Exception)]
    assert statuses.count(201) == 1, f"expected exactly one winner, got statuses={statuses}"
    assert statuses.count(409) == 2, f"expected exactly two conflicts, got statuses={statuses}"

    # The slot itself agrees: exactly one appointment now holds it.
    slot_doc = await world.slot_doc(slot["id"])
    assert slot_doc["status"] == "HELD"
    active = await world.db["appointments"].count_documents({"slot_id": slot_doc["_id"], "is_active": True})
    assert active == 1


async def test_concurrent_accept_and_cancel_only_one_wins(world):
    """Doctor accepting while the patient cancels at the same moment: exactly one transition wins."""
    await world.add_window(world.d1)
    slot = await world.slot_at(world.d1, "09:00")
    r = await world.request(world.p1, slot["id"])
    assert r.status_code == 201, r.text
    appt_id = r.json()["id"]

    results = await asyncio.gather(
        world.api("POST", f"/appointments/{appt_id}/accept", world.d1, json={}),
        world.api("POST", f"/appointments/{appt_id}/cancel", world.p1, json={}),
        return_exceptions=True,
    )
    statuses = sorted(r.status_code for r in results if not isinstance(r, Exception))
    # Exactly one of the two racing transitions succeeds; the other is rejected as a conflict.
    assert statuses == [200, 409], f"expected one winner and one conflict, got {statuses}"

    final = await world.api("GET", f"/appointments/{appt_id}", world.p1)
    assert final.json()["status"] in ("CONFIRMED", "CANCELLED")
