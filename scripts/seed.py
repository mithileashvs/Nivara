"""Development seed data for Nivara.

Populates a small, realistic scenario through the SAME public REST API the frontend would use
(via an in-process ASGI client — no server needs to be running), so every record goes through the
real validation, affiliation and slot-generation logic. The only exception is the very first admin
account, which — like the rest of the platform — cannot be created through the API (admins are only
ever created by an existing admin), so it is inserted directly, exactly as `tests/helpers.py` does.

Usage:

    python scripts/seed.py

Safe to run more than once: every step checks whether its record already exists (by email / name /
date+time) before creating it, so re-running does not create duplicates. Requires DATABASE_URL
configured in your environment / `.env`.

Never uses real personal data. All accounts use the same development password (see PASSWORD below)
and @nivara.local / @smartcare.local email addresses that cannot receive real mail.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, timedelta

import httpx

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.connection import DatabaseManager
from app.database.indexes import ensure_indexes
from app.main import create_app
from app.models.enums import UserRole
from app.models.users import User
from app.services.department_routing_service import DepartmentRoutingService

logging.basicConfig(level=logging.WARNING)  # keep seed output readable; suppress app request logs

PREFIX = "/api/v1"
PASSWORD = "DevPass123!"  # development only — never used in production
ADMIN_EMAIL = "admin@nivara.com"



def line(msg: str) -> None:
    print(f"  {msg}")


class Seeder:
    def __init__(self, client: httpx.AsyncClient, db) -> None:
        self.client = client
        self.db = db
        self.created: list[str] = []
        self.skipped: list[str] = []

    async def api(self, method: str, path: str, headers: dict | None = None, **kw) -> httpx.Response:
        return await self.client.request(method, PREFIX + path, headers=headers or {}, **kw)

    async def login(self, email: str) -> dict:
        r = await self.api("POST", "/auth/login", json={"email": email, "password": PASSWORD})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    # ---------------------------------------------------------------- admin (bootstrap only)

    async def ensure_admin(self) -> dict:
        existing = await self.db["users"].find_one({"email": ADMIN_EMAIL})
        if existing is None:
            user = User(
                name="Platform Admin", email=ADMIN_EMAIL, password_hash=hash_password(PASSWORD, 12), role=UserRole.ADMIN,
                managed_hospital_ids=None,
            ).to_mongo()
            await self.db["users"].insert_one(user)
            self.created.append(f"admin {ADMIN_EMAIL}")
        else:
            self.skipped.append(f"admin {ADMIN_EMAIL} (already exists)")
        headers = await self.login(ADMIN_EMAIL)
        return {"email": ADMIN_EMAIL, "headers": headers}

    # ---------------------------------------------------------------- hospitals / departments

    async def ensure_hospital(self, admin: dict, name: str, city: str, lat: float, lon: float) -> dict:
        existing = await self.db["hospitals"].find_one({"name": name})
        if existing is not None:
            self.skipped.append(f"hospital '{name}' (already exists)")
            return {"id": str(existing["_id"]), "name": name}
        r = await self.api("POST", "/hospitals", admin["headers"], json={
            "name": name, "address": f"1 {name} Road", "location": {"city": city, "latitude": lat, "longitude": lon},
        })
        r.raise_for_status()
        self.created.append(f"hospital '{name}'")
        return r.json()

    async def ensure_department(self, admin: dict, hospital_id: str, name: str) -> dict:
        existing = await self.db["departments"].find_one({"hospital_id": hospital_id, "name": name})
        if existing is not None:
            self.skipped.append(f"department '{name}' (already exists)")
            return {"id": str(existing["_id"]), "name": name}
        r = await self.api("POST", "/departments", admin["headers"], json={"hospital_id": hospital_id, "name": name})
        r.raise_for_status()
        self.created.append(f"department '{name}'")
        return r.json()

    # ---------------------------------------------------------------- people

    async def ensure_patient(self, name: str, email: str, **extra) -> dict:
        existing = await self.db["users"].find_one({"email": email})
        if existing is None:
            r = await self.api("POST", "/auth/register", json={
                "name": name, "email": email, "password": PASSWORD, "role": "PATIENT", **extra,
            })
            r.raise_for_status()
            self.created.append(f"patient {email}")
        else:
            self.skipped.append(f"patient {email} (already exists)")
        headers = await self.login(email)
        profile = (await self.api("GET", "/patients/me", headers)).json()
        return {"id": profile["id"], "name": name, "email": email, "headers": headers}

    async def ensure_doctor(self, admin: dict, name: str, email: str, specialty: str, hospital_id: str, department_id: str, **extra) -> dict:
        existing = await self.db["users"].find_one({"email": email})
        if existing is None:
            r = await self.api("POST", "/auth/register", json={
                "name": name, "email": email, "password": PASSWORD, "role": "DOCTOR", "specialty": specialty, **extra,
            })
            r.raise_for_status()
            self.created.append(f"doctor {email}")
        else:
            self.skipped.append(f"doctor {email} (already exists)")
        headers = await self.login(email)
        profile = (await self.api("GET", "/doctors/me", headers)).json()
        doctor_id = profile["id"]
        # Affiliate + activate (idempotent: PUT sets absolute state either way).
        r = await self.api("PUT", f"/admin/doctors/{doctor_id}/affiliations", admin["headers"],
                            json={"hospital_ids": [hospital_id], "department_ids": [department_id]})
        r.raise_for_status()
        if profile["profile_status"] != "ACTIVE":
            r = await self.api("PUT", f"/admin/doctors/{doctor_id}/profile-status", admin["headers"], json={"profile_status": "ACTIVE"})
            r.raise_for_status()
        return {"id": doctor_id, "name": name, "email": email, "headers": headers, "hospital_id": hospital_id, "department_id": department_id}

    # ---------------------------------------------------------------- availability / slots

    async def ensure_availability(self, doctor: dict, day: date, start: str = "09:00", end: str = "13:00") -> None:
        existing = await self.db["doctor_availability"].find_one({
            "doctor_id": doctor["id"], "date": day.isoformat(), "start_time": start, "status": "WORKING",
        })
        if existing is not None:
            self.skipped.append(f"availability for {doctor['name']} on {day} (already exists)")
            return
        r = await self.api("POST", "/doctors/me/availability", doctor["headers"], json={
            "hospital_id": doctor["hospital_id"], "department_id": doctor["department_id"], "date": day.isoformat(),
            "start_time": start, "end_time": end, "slot_duration": 30, "status": "WORKING",
        })
        r.raise_for_status()
        n = r.json()["slots_created"]
        self.created.append(f"availability for {doctor['name']} on {day} ({n} slots)")

    async def first_open_slot(self, doctor: dict, day: date) -> dict | None:
        r = await self.api("GET", f"/slots/me?date_from={day.isoformat()}&date_to={day.isoformat()}&status=AVAILABLE&page_size=10", doctor["headers"])
        r.raise_for_status()
        items = r.json()["items"]
        return items[0] if items else None

    # ---------------------------------------------------------------- sample appointments

    async def ensure_appointment(self, patient: dict, doctor: dict, day: date, *, decision: str | None) -> None:
        """decision: None (leave REQUESTED), 'accept', or 'reject'."""
        already = await self.db["appointments"].count_documents({
            "patient_id": patient["id"], "doctor_id": doctor["id"], "appointment_date": day.isoformat(),
        })
        if already:
            self.skipped.append(f"appointment {patient['name']} <-> {doctor['name']} on {day} (already exists)")
            return
        slot = await self.first_open_slot(doctor, day)
        if slot is None:
            line(f"  (no open slot for {doctor['name']} on {day}, skipping sample appointment)")
            return
        r = await self.api("POST", "/appointments", patient["headers"], json={
            "slot_id": slot["id"], "consultation_type": "FIRST_VISIT", "reason": "Development seed data",
        })
        r.raise_for_status()
        appt = r.json()
        if decision == "accept":
            r = await self.api("POST", f"/appointments/{appt['id']}/accept", doctor["headers"], json={})
            r.raise_for_status()
        elif decision == "reject":
            r = await self.api("POST", f"/appointments/{appt['id']}/reject", doctor["headers"], json={"reason": "Fully booked that day"})
            r.raise_for_status()
        self.created.append(f"appointment {patient['name']} <-> {doctor['name']} on {day} ({decision or 'requested'})")


async def main() -> None:
    import os
    from app.core.config import Settings
    try:
        settings = get_settings()
    except Exception:
        settings = Settings(
            database_url=os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres@127.0.0.1:5433/postgres"),
            database_name="nivara",
            jwt_secret="dev-seed-secret-key-that-is-at-least-32-chars-long",
            environment="development",
        )
    settings.rate_limit_enabled = False
    manager = DatabaseManager(settings)
    db = await manager.connect()
    await ensure_indexes(db)
    await DepartmentRoutingService(db).ensure_default_rules()

    app = create_app(settings, db=db)  # reuse the real app/routes; skip its own DB connection
    transport = httpx.ASGITransport(app=app)

    print("Seeding Nivara development data into database ...")
    async with httpx.AsyncClient(transport=transport, base_url="http://seed") as client:
        s = Seeder(client, db)

        admin = await s.ensure_admin()

        h1 = await s.ensure_hospital(admin, "City General Hospital", "Chennai", 13.0827, 80.2707)
        h2 = await s.ensure_hospital(admin, "Lakeside Multispecialty Clinic", "Tiruchirappalli", 10.7905, 78.7047)

        d_h1_general = await s.ensure_department(admin, h1["id"], "General Medicine")
        d_h1_cardio = await s.ensure_department(admin, h1["id"], "Cardiology")
        d_h1_derma = await s.ensure_department(admin, h1["id"], "Dermatology")
        d_h2_general = await s.ensure_department(admin, h2["id"], "General Medicine")
        d_h2_ortho = await s.ensure_department(admin, h2["id"], "Orthopedics")

        doctors = [
            await s.ensure_doctor(admin, "Dr. Asha Rao", "doctor1@nivara.com", "General Medicine", h1["id"], d_h1_general["id"], experience=10, consultation_fee=300),
            await s.ensure_doctor(admin, "Dr. Ravi Kumar", "doctor2@nivara.com", "Cardiology", h1["id"], d_h1_cardio["id"], experience=15, consultation_fee=800),
            await s.ensure_doctor(admin, "Dr. Meena Iyer", "doctor3@nivara.com", "Dermatology", h1["id"], d_h1_derma["id"], experience=6, consultation_fee=500),
            await s.ensure_doctor(admin, "Dr. Suresh Babu", "doctor4@nivara.com", "General Medicine", h2["id"], d_h2_general["id"], experience=4, consultation_fee=250),
            await s.ensure_doctor(admin, "Dr. Priya Nathan", "doctor5@nivara.com", "Orthopedics", h2["id"], d_h2_ortho["id"], experience=8, consultation_fee=600),
        ]

        patients = [
            await s.ensure_patient("Test Patient One", "patient1@nivara.com", date_of_birth="1990-05-01", gender="FEMALE"),
            await s.ensure_patient("Test Patient Two", "patient2@nivara.com", date_of_birth="1985-11-20", gender="MALE"),
            await s.ensure_patient("Test Patient Three", "patient3@nivara.com"),
            await s.ensure_patient("Test Patient Four", "patient4@nivara.com"),
            await s.ensure_patient("Test Patient Five", "patient5@nivara.com"),
        ]

        today = date.today()
        days = [today + timedelta(days=1), today + timedelta(days=2), today + timedelta(days=3)]
        for doctor in doctors:
            for day in days:
                await s.ensure_availability(doctor, day)

        # A few sample appointments across different lifecycle states.
        await s.ensure_appointment(patients[0], doctors[0], days[0], decision="accept")   # CONFIRMED
        await s.ensure_appointment(patients[1], doctors[0], days[0], decision=None)       # REQUESTED (pending)
        await s.ensure_appointment(patients[2], doctors[1], days[1], decision="accept")   # CONFIRMED
        await s.ensure_appointment(patients[3], doctors[2], days[1], decision="reject")   # REJECTED
        await s.ensure_appointment(patients[4], doctors[3], days[2], decision=None)       # REQUESTED (pending)

    print(f"\nCreated {len(s.created)} record(s):")
    for item in s.created:
        line(item)
    print(f"\nSkipped {len(s.skipped)} record(s) that already existed:")
    for item in s.skipped:
        line(item)

    print("\nDevelopment credentials (password for every account: " + PASSWORD + "):")
    line(f"admin:    {ADMIN_EMAIL}")
    for doc in doctors:
        line(f"doctor:   {doc['email']}  ({doc['name']})")
    for pat in patients:
        line(f"patient:  {pat['email']}  ({pat['name']})")

    await manager.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:  # noqa: BLE001
        print(f"\nSeed script failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
