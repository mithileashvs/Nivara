"""Admin platform-wide statistics: every number is a real, live database count."""


async def test_admin_statistics_reflects_real_counts(world):
    await world.add_window(world.d1)
    confirmed = await world.book(world.p1, world.d1, "09:00", confirm=True)
    slot2 = await world.slot_at(world.d1, "09:30")
    r = await world.request(world.p2, slot2["id"])
    assert r.status_code == 201, r.text

    r = await world.api("GET", "/admin/statistics", world.admin)
    assert r.status_code == 200, r.text
    stats = r.json()

    assert stats["total_hospitals"] == 2
    assert stats["total_departments"] == 4
    assert stats["total_doctors"] == 3
    assert stats["total_patients"] == 3
    assert stats["total_appointments"] == 2
    assert stats["confirmed_appointments"] == 1
    assert stats["requested_appointments"] == 1
    assert stats["completed_appointments"] == 0
    assert stats["cancelled_appointments"] == 0


async def test_admin_statistics_requires_platform_admin(world):
    r = await world.api("GET", "/admin/statistics", world.h1_admin)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "platform_admin_required"


async def test_admin_statistics_requires_admin_role(world):
    r = await world.api("GET", "/admin/statistics", world.p1)
    assert r.status_code == 403, r.text
