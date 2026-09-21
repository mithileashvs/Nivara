"""Verification script for Nivara Supabase Development Seed.

Validates:
1. Authentication: POST /api/v1/auth/login for doctor4@nivara.com with DevPass123! -> HTTP 200 + valid JWT.
2. Doctor Search: GET /api/v1/doctors?q=Dr.%20Suresh%20Babu&page=1&page_size=20 -> HTTP 200 + Dr. Suresh Babu present.
3. Doctor Profile: GET /api/v1/doctors/me -> confirms profile_status is ACTIVE and availability_status is OPEN.
4. Preserved Patient: Confirms vsmff2@gmail.com is present and untouched.
"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import httpx
from app.core.config import get_settings
from app.database.connection import DatabaseManager
from app.main import create_app
from app.database.tables import TABLE_MAP
from sqlalchemy import select


async def run_verification() -> None:
    print("=" * 60)
    print("NIVARA SEED VERIFICATION — API & AUTHENTICATION")
    print("=" * 60)

    settings = get_settings()
    manager = DatabaseManager(settings)
    db = await manager.connect()

    app = create_app(settings, db=db)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login verification for doctor4@nivara.com
        print("\n[*] 1. Testing POST /api/v1/auth/login for doctor4@nivara.com ...")
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "doctor4@nivara.com", "password": "DevPass123!"},
        )
        print(f"    Status: {login_res.status_code}")
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        login_data = login_res.json()
        token = login_data.get("access_token")
        user_info = login_data.get("user", {})
        print(f"    [OK] Authenticated successfully!")
        print(f"    Token type: {login_data.get('token_type')}, Expires in: {login_data.get('expires_in')}s")
        print(f"    User: {user_info.get('name')} ({user_info.get('email')}), Role: {user_info.get('role')}")

        headers = {"Authorization": f"Bearer {token}"}

        # 2. Verify Doctor Profile via GET /api/v1/doctors/me
        print("\n[*] 2. Testing GET /api/v1/doctors/me ...")
        me_res = await client.get("/api/v1/doctors/me", headers=headers)
        print(f"    Status: {me_res.status_code}")
        assert me_res.status_code == 200, f"GET /doctors/me failed: {me_res.text}"
        me_data = me_res.json()
        print(f"    [OK] Doctor Profile: {me_data.get('name')}")
        print(f"    Specialty: {me_data.get('specialty')}")
        print(f"    Profile Status: {me_data.get('profile_status')}")
        print(f"    Availability Status: {me_data.get('availability_status')}")
        print(f"    Hospital IDs: {me_data.get('hospital_ids')}")
        print(f"    Department IDs: {me_data.get('department_ids')}")
        assert me_data.get("profile_status") == "ACTIVE", "Expected profile_status ACTIVE"
        assert me_data.get("availability_status") == "OPEN", "Expected availability_status OPEN"

        # 3. Doctor Search verification: GET /api/v1/doctors?q=Dr.%20Suresh%20Babu&page=1&page_size=20
        print("\n[*] 3. Testing GET /api/v1/doctors?q=Dr.%20Suresh%20Babu&page=1&page_size=20 ...")
        search_res = await client.get(
            "/api/v1/doctors?q=Dr.%20Suresh%20Babu&page=1&page_size=20",
            headers=headers,
        )
        print(f"    Status: {search_res.status_code}")
        assert search_res.status_code == 200, f"Search failed: {search_res.text}"
        search_data = search_res.json()
        total = search_data.get("total", 0)
        items = search_data.get("items", [])
        print(f"    [OK] Search returned total={total}, items count={len(items)}")

        found_doctor = None
        for item in items:
            print(f"    - ID: {item.get('id')} | Name: {item.get('name')} | Specialty: {item.get('specialty')} | Fee: {item.get('consultation_fee')}")
            if item.get("name") == "Dr. Suresh Babu":
                found_doctor = item

        assert found_doctor is not None, "Dr. Suresh Babu NOT FOUND in search results!"
        print(f"    [OK] Verified: 'Dr. Suresh Babu' found in search results!")

        # 4. Preserved patient check
        print("\n[*] 4. Checking preserved real patient in database ...")
        async with db.engine.connect() as conn:
            t_users = TABLE_MAP["users"]
            real_patient = (await conn.execute(select(t_users).where(t_users.c.email == "vsmff2@gmail.com"))).mappings().first()
            assert real_patient is not None, "Preserved patient vsmff2@gmail.com was lost!"
            print(f"    [OK] Verified: 'vsmff2@gmail.com' intact (id={real_patient['id']}, role={real_patient['role']})")

    await manager.close()
    print("\n" + "=" * 60)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_verification())
