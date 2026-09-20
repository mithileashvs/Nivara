from datetime import date, datetime, timedelta, timezone
from typing import Any

from bson import ObjectId

from app.core.security import hash_password
from app.models.users import User
from app.models.enums import UserRole

PREFIX = "/api/v1"
PASSWORD = "Str0ngPass!"


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


class Person:
    def __init__(self, id: str, user_id: str, name: str, email: str, headers: dict, profile_id: str) -> None:
        self.id, self.user_id, self.name, self.email, self.headers, self.profile_id = id, user_id, name, email, headers, profile_id


class World:
    """A ready-made scenario created through the public API:

    * platform admin, plus a hospital-scoped admin for hospital 1
    * hospital 1 (General Medicine, Cardiology, Dermatology) and hospital 2 (General Medicine)
    * doctor 1 (General Medicine @ H1), doctor 2 (Dermatology @ H1), doctor 3 (General Medicine @ H2)
    * three patients
    """

    def __init__(self, client, db, settings) -> None:
        self.client, self.db, self.settings = client, db, settings
        self.tomorrow = today_utc() + timedelta(days=1)

    # ---------- raw API ----------
    async def api(self, method: str, path: str, who: Person | dict | None = None, **kw):
        headers = kw.pop("headers", None) or (who.headers if isinstance(who, Person) else who) or {}
        return await self.client.request(method, PREFIX + path, headers=headers, **kw)

    # ---------- people ----------
    async def _login(self, email: str, password: str = PASSWORD) -> dict:
        r = await self.api("POST", "/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    async def register_patient(self, name: str, email: str, **extra) -> Person:
        r = await self.api("POST", "/auth/register", json={"name": name, "email": email, "password": PASSWORD, "role": "PATIENT", **extra})
        assert r.status_code == 201, r.text
        headers = await self._login(email)
        prof = (await self.api("GET", "/patients/me", headers=headers)).json()
        return Person(prof["id"], r.json()["id"], name, email, headers, prof["id"])

    async def register_doctor(self, name: str, email: str, specialty: str, **extra) -> Person:
        r = await self.api("POST", "/auth/register", json={"name": name, "email": email, "password": PASSWORD, "role": "DOCTOR", "specialty": specialty, **extra})
        assert r.status_code == 201, r.text
        headers = await self._login(email)
        prof = (await self.api("GET", "/doctors/me", headers=headers)).json()
        return Person(prof["id"], r.json()["id"], name, email, headers, prof["id"])

    async def create_admin_direct(self, email: str, managed_hospital_ids: list[str] | None = None) -> Person:
        user = User(name="Admin " + email.split("@")[0], email=email, password_hash=hash_password(PASSWORD, 4), role=UserRole.ADMIN,
                    managed_hospital_ids=[ObjectId(h) for h in managed_hospital_ids] if managed_hospital_ids is not None else None).to_mongo()
        await self.db["users"].insert_one(user)
        return Person(str(user["_id"]), str(user["_id"]), user["name"], email, await self._login(email), str(user["_id"]))

    async def activate_doctor(self, doctor: Person, hospital_ids: list[str], department_ids: list[str]) -> None:
        r = await self.api("PUT", f"/admin/doctors/{doctor.id}/affiliations", self.admin, json={"hospital_ids": hospital_ids, "department_ids": department_ids})
        assert r.status_code == 200, r.text
        r = await self.api("PUT", f"/admin/doctors/{doctor.id}/profile-status", self.admin, json={"profile_status": "ACTIVE"})
        assert r.status_code == 200, r.text

    # ---------- scenario ----------
    async def build(self) -> None:
        self.admin = await self.create_admin_direct("root@smartcare-demo.com")
        self.hospital = {}
        self.dept = {}
        for key, name, city, lat, lon in (("h1", "City Care Hospital", "Chennai", 13.0827, 80.2707), ("h2", "Lakeside Clinic", "Trichy", 10.7905, 78.7047)):
            r = await self.api("POST", "/hospitals", self.admin, json={"name": name, "address": "1 Test Road", "location": {"city": city, "latitude": lat, "longitude": lon}})
            assert r.status_code == 201, r.text
            self.hospital[key] = r.json()
        for hk, dn in (("h1", "General Medicine"), ("h1", "Cardiology"), ("h1", "Dermatology"), ("h2", "General Medicine")):
            r = await self.api("POST", "/departments", self.admin, json={"hospital_id": self.hospital[hk]["id"], "name": dn})
            assert r.status_code == 201, r.text
            self.dept[f"{hk}_{dn.split()[0].lower()}"] = r.json()
        self.h1_admin = await self.create_admin_direct("h1admin@smartcare-demo.com", [self.hospital["h1"]["id"]])

        self.d1 = await self.register_doctor("Dr. Asha Rao", "asha@smartcare-demo.com", "General Medicine", experience=10, consultation_fee=300)
        self.d2 = await self.register_doctor("Dr. Ravi Kumar", "ravi@smartcare-demo.com", "Dermatology", experience=6, consultation_fee=500)
        self.d3 = await self.register_doctor("Dr. Meena Iyer", "meena@smartcare-demo.com", "General Medicine", experience=4, consultation_fee=250)
        await self.activate_doctor(self.d1, [self.hospital["h1"]["id"]], [self.dept["h1_general"]["id"]])
        await self.activate_doctor(self.d2, [self.hospital["h1"]["id"]], [self.dept["h1_dermatology"]["id"]])
        await self.activate_doctor(self.d3, [self.hospital["h2"]["id"]], [self.dept["h2_general"]["id"]])

        self.p1 = await self.register_patient("Test Patient One", "p1@smartcare-demo.com", date_of_birth="1990-05-01", gender="FEMALE")
        self.p2 = await self.register_patient("Test Patient Two", "p2@smartcare-demo.com")
        self.p3 = await self.register_patient("Test Patient Three", "p3@smartcare-demo.com")

    # ---------- scheduling helpers ----------
    async def add_window(self, doctor: Person, *, hospital: str = "h1", dept: str = "h1_general", day: date | None = None,
                         start: str = "09:00", end: str = "12:00", duration: int = 30, status: str = "WORKING"):
        return await self.api("POST", "/doctors/me/availability", doctor, json={
            "hospital_id": self.hospital[hospital]["id"], "department_id": self.dept[dept]["id"], "date": (day or self.tomorrow).isoformat(),
            "start_time": start, "end_time": end, "slot_duration": duration, "status": status})

    async def slots(self, doctor: Person, day: date | None = None, status: str | None = None) -> list[dict]:
        d = (day or self.tomorrow).isoformat()
        q = f"?date_from={d}&date_to={d}&page_size=100" + (f"&status={status}" if status else "")
        r = await self.api("GET", "/slots/me" + q, doctor)
        assert r.status_code == 200, r.text
        return r.json()["items"]

    async def slot_at(self, doctor: Person, start_time: str, day: date | None = None) -> dict:
        return next(s for s in await self.slots(doctor, day) if s["start_time"] == start_time)

    async def request(self, patient: Person, slot_id: str, ctype: str = "FIRST_VISIT", reason: str | None = None):
        return await self.api("POST", "/appointments", patient, json={"slot_id": slot_id, "consultation_type": ctype, "reason": reason})

    async def book(self, patient: Person, doctor: Person, start_time: str = "09:00", confirm: bool = False) -> dict:
        slot = await self.slot_at(doctor, start_time)
        r = await self.request(patient, slot["id"])
        assert r.status_code == 201, r.text
        appt = r.json()
        if confirm:
            r = await self.api("POST", f"/appointments/{appt['id']}/accept", doctor, json={})
            assert r.status_code == 200, r.text
            appt = r.json()
        return appt

    async def slot_doc(self, slot_id: str) -> dict:
        return await self.db["appointment_slots"].find_one({"_id": ObjectId(slot_id)})

    async def notifications(self, person: Person, type: str | None = None) -> list[dict]:
        r = await self.api("GET", "/notifications?page_size=100", person)
        items = r.json()["items"]
        return [n for n in items if type is None or n["type"] == type]

    async def make_started(self, appointment_id: str) -> None:
        """Move an appointment (and its slot) into the past so it can be completed / marked no-show."""
        appt = await self.db["appointments"].find_one({"_id": ObjectId(appointment_id)})
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        await self.db["appointments"].update_one({"_id": appt["_id"]}, {"$set": {"start_at": past, "end_at": past + timedelta(minutes=30)}})
        await self.db["appointment_slots"].update_one({"_id": appt["slot_id"]}, {"$set": {"start_at": past, "end_at": past + timedelta(minutes=30)}})
