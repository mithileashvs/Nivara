"""Basic department suggestion: symptom -> department routing only, never diagnosis/prescription."""


async def test_department_suggestion_returns_department_and_disclaimer(world):
    r = await world.api("POST", "/smart/department-suggestion", world.p1, json={"symptoms": ["fever", "headache"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["primary_department"]
    assert body["disclaimer"]
    assert isinstance(body["suggested_departments"], list)


async def test_department_suggestion_requires_auth(world):
    r = await world.api("POST", "/smart/department-suggestion", json={"symptoms": ["fever"]})
    assert r.status_code == 401, r.text


async def test_department_suggestion_rejects_empty_symptoms(world):
    r = await world.api("POST", "/smart/department-suggestion", world.p1, json={"symptoms": []})
    assert r.status_code == 422, r.text
