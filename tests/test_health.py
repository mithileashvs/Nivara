"""Liveness and readiness endpoints."""


async def test_health(world):
    r = await world.api("GET", "/health")
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "ok"}


async def test_health_ready(world):
    r = await world.api("GET", "/health/ready")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"
    assert r.json()["database"] == "up"
