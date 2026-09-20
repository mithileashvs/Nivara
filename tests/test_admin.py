"""Admin basic platform management: users, patients, doctors, hospitals, departments — never appointment approval."""


async def test_admin_can_list_users(world):
    r = await world.api("GET", "/admin/users", world.admin)
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 3  # 2 admins + at least the doctors/patients created


async def test_admin_can_filter_users_by_role(world):
    r = await world.api("GET", "/admin/users?role=DOCTOR", world.admin)
    assert r.status_code == 200, r.text
    assert all(u["role"] == "DOCTOR" for u in r.json()["items"])
    assert r.json()["total"] == 3


async def test_admin_can_view_patients(world):
    r = await world.api("GET", "/patients", world.admin)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 3


async def test_admin_can_view_doctors_including_pending(world):
    pending = await world.register_doctor("Dr. Newcomer", "newcomer@smartcare-demo.com", "General Medicine")
    r = await world.api("GET", "/admin/doctors?profile_status=PENDING", world.admin)
    assert r.status_code == 200, r.text
    names = {d["name"] for d in r.json()["items"]}
    assert pending.name in names


async def test_admin_can_verify_a_pending_doctor(world):
    pending = await world.register_doctor("Dr. Verifiable", "verifiable@smartcare-demo.com", "General Medicine")
    r = await world.api("PUT", f"/admin/doctors/{pending.id}/profile-status", world.admin, json={"profile_status": "ACTIVE"})
    assert r.status_code == 200, r.text
    assert r.json()["profile_status"] == "ACTIVE"


async def test_admin_can_suspend_a_doctor(world):
    r = await world.api("PUT", f"/admin/doctors/{world.d1.id}/profile-status", world.admin, json={"profile_status": "SUSPENDED"})
    assert r.status_code == 200, r.text
    assert r.json()["profile_status"] == "SUSPENDED"


async def test_admin_can_set_doctor_affiliations(world):
    r = await world.api("PUT", f"/admin/doctors/{world.d1.id}/affiliations", world.admin, json={
        "hospital_ids": [world.hospital["h1"]["id"]], "department_ids": [world.dept["h1_cardiology"]["id"]],
    })
    assert r.status_code == 200, r.text
    assert r.json()["department_ids"] == [world.dept["h1_cardiology"]["id"]]


async def test_admin_can_view_and_manage_hospitals(world):
    r = await world.api("GET", "/hospitals", world.admin)
    assert r.status_code == 200, r.text
    r = await world.api("PATCH", f"/hospitals/{world.hospital['h1']['id']}", world.admin, json={"address": "New Address"})
    assert r.status_code == 200, r.text
    assert r.json()["address"] == "New Address"


async def test_admin_can_view_and_manage_departments(world):
    r = await world.api("GET", "/departments", world.admin)
    assert r.status_code == 200, r.text
    r = await world.api("PATCH", f"/departments/{world.dept['h1_general']['id']}", world.admin, json={"description": "Primary care"})
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "Primary care"


async def test_admin_can_deactivate_and_reactivate_a_user(world):
    r = await world.api("PUT", f"/admin/users/{world.p1.user_id}/active", world.admin, json={"is_active": False})
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    r = await world.api("PUT", f"/admin/users/{world.p1.user_id}/active", world.admin, json={"is_active": True})
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is True


async def test_admin_cannot_deactivate_self(world):
    r = await world.api("PUT", f"/admin/users/{world.admin.user_id}/active", world.admin, json={"is_active": False})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "cannot_modify_self"


async def test_admin_create_second_admin(world):
    r = await world.api("POST", "/admin/users", world.admin, json={
        "name": "Second Admin", "email": "second-admin@smartcare-demo.com", "password": "Str0ngPass!",
    })
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "ADMIN"
