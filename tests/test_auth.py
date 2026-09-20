"""Authentication: registration, login, JWT validation, protected-endpoint access."""


async def test_register_patient(world):
    r = await world.api("POST", "/auth/register", json={
        "name": "New Patient", "email": "newpatient@test.com", "password": "Str0ngPass!", "role": "PATIENT",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "newpatient@test.com"
    assert body["role"] == "PATIENT"
    assert "password" not in body and "password_hash" not in body


async def test_register_doctor_requires_specialty(world):
    r = await world.api("POST", "/auth/register", json={
        "name": "New Doc", "email": "newdoc@test.com", "password": "Str0ngPass!", "role": "DOCTOR",
    })
    assert r.status_code == 422, r.text


async def test_duplicate_registration_rejected(world):
    payload = {"name": "Dup", "email": "dup@test.com", "password": "Str0ngPass!", "role": "PATIENT"}
    r1 = await world.api("POST", "/auth/register", json=payload)
    assert r1.status_code == 201, r1.text
    r2 = await world.api("POST", "/auth/register", json=payload)
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "email_taken"


async def test_admin_cannot_self_register(world):
    r = await world.api("POST", "/auth/register", json={
        "name": "Sneaky", "email": "sneaky@test.com", "password": "Str0ngPass!", "role": "ADMIN",
    })
    assert r.status_code == 422, r.text


async def test_login_success(world):
    r = await world.api("POST", "/auth/login", json={"email": world.p1.email, "password": "Str0ngPass!"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == world.p1.email


async def test_login_invalid_password(world):
    r = await world.api("POST", "/auth/login", json={"email": world.p1.email, "password": "WrongPass1!"})
    assert r.status_code == 401, r.text
    assert r.json()["error"]["code"] == "invalid_credentials"


async def test_login_unknown_email(world):
    r = await world.api("POST", "/auth/login", json={"email": "nobody@test.com", "password": "Str0ngPass!"})
    assert r.status_code == 401, r.text


async def test_protected_endpoint_without_token(world):
    r = await world.api("GET", "/patients/me")
    assert r.status_code == 401, r.text
    assert r.json()["error"]["code"] == "not_authenticated"


async def test_protected_endpoint_with_garbage_token(world):
    r = await world.api("GET", "/patients/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401, r.text
    assert r.json()["error"]["code"] == "invalid_token"


async def test_deactivated_user_loses_access(world):
    r = await world.api("PUT", f"/admin/users/{world.p1.user_id}/active", world.admin, json={"is_active": False})
    assert r.status_code == 200, r.text
    r = await world.api("GET", "/patients/me", world.p1)
    assert r.status_code == 401, r.text


async def test_me_endpoint(world):
    r = await world.api("GET", "/auth/me", world.p1)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == world.p1.email
