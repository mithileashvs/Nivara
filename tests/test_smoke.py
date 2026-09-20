async def test_world_builds_and_health(world, client):
    assert (await client.get("/health")).json() == {"status": "ok"}
    r = await world.add_window(world.d1)
    assert r.status_code == 201, r.text
    assert r.json()["slots_created"] == 6
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)
    assert appt["status"] == "CONFIRMED"
