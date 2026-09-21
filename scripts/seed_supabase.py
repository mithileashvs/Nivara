"""Dedicated Supabase PostgreSQL Development Seed Script for Nivara.

Populates a complete, realistic development scenario directly into Supabase PostgreSQL:
- Admin account (admin@nivara.com)
- 2 Hospitals (City General Hospital, Lakeside Multispecialty Clinic)
- 5 Departments (General Medicine, Cardiology, Dermatology, Orthopedics)
- 5 Doctors with affiliations & ACTIVE/OPEN status (including Dr. Suresh Babu / doctor4@nivara.com)
- 5 Patients (patient1@nivara.com .. patient5@nivara.com)
- Doctor availability across upcoming dates (09:00-13:00, 30m slots)
- Appointment slots with timezone-consistent UTC timestamps
- 5 Sample appointments representing different lifecycle states:
  1. CONFIRMED (slot BOOKED)
  2. REQUESTED (slot HELD)
  3. CONFIRMED (slot BOOKED)
  4. REJECTED (slot released to AVAILABLE)
  5. REQUESTED (slot HELD)

Guarantees:
- Safe & Idempotent: Uses compound uniqueness keys to detect existing records.
- Zero overwrite of existing doctor affiliations or status.
- Real patient 'vsmff2@gmail.com' and symptom_routing_rules remain completely untouched.
- Environment safety guard: refuses to run in production without --allow-production-seed.
- Proper bcrypt password hashing via app.core.security.hash_password.
- Never drops or truncates tables.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# Ensure project root is on sys.path when run as `python scripts/seed_supabase.py`
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import and_, func, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.connection import DatabaseManager
from app.database.tables import TABLE_MAP
from app.utils.text import normalize
from app.utils.time_utils import local_to_utc, today_local, utcnow

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_supabase")

PASSWORD = "DevPass123!"
ADMIN_EMAIL = "admin@nivara.com"
PRESERVED_PATIENT_EMAIL = "vsmff2@gmail.com"

REQUIRED_TABLES = [
    "users",
    "patients",
    "doctors",
    "hospitals",
    "departments",
    "doctor_availability",
    "appointment_slots",
    "appointments",
    "appointment_history",
    "medical_records",
    "reviews",
    "notifications",
    "waitlist_entries",
    "symptom_routing_rules",
    "intake_events",
]


class Seeder:
    def __init__(self, db, settings) -> None:
        self.db = db
        self.settings = settings
        self.created: list[str] = []
        self.skipped: list[str] = []

    def log_created(self, msg: str) -> None:
        self.created.append(msg)
        print(f"  [CREATED] {msg}")

    def log_skipped(self, msg: str) -> None:
        self.skipped.append(msg)
        print(f"  [SKIPPED] {msg}")

    # ------------------------------------------------------------------ Admin
    async def ensure_admin(self) -> dict:
        t_users = TABLE_MAP["users"]
        async with self.db.engine.connect() as conn:
            row = (await conn.execute(select(t_users).where(t_users.c.email == ADMIN_EMAIL))).mappings().first()
            if row:
                self.log_skipped(f"Admin {ADMIN_EMAIL} (already exists)")
                return dict(row)

        now = utcnow()
        admin_id = str(uuid4())
        hashed = hash_password(PASSWORD, rounds=self.settings.bcrypt_rounds)
        insert_data = {
            "id": admin_id,
            "name": "Platform Admin",
            "email": ADMIN_EMAIL,
            "password_hash": hashed,
            "phone": None,
            "role": "ADMIN",
            "is_active": True,
            "managed_hospital_ids": None,
            "created_at": now,
            "updated_at": now,
        }
        async with self.db.engine.begin() as conn:
            await conn.execute(t_users.insert().values(insert_data))
        self.log_created(f"Admin {ADMIN_EMAIL}")
        return insert_data

    # ------------------------------------------------------------------ Hospitals
    async def ensure_hospital(self, name: str, city: str, lat: float, lon: float, address: str, phone: str) -> dict:
        t_hosp = TABLE_MAP["hospitals"]
        norm_name = normalize(name)
        async with self.db.engine.connect() as conn:
            row = (await conn.execute(select(t_hosp).where(t_hosp.c.name_normalized == norm_name))).mappings().first()
            if row:
                self.log_skipped(f"Hospital '{name}' (already exists)")
                return dict(row)

        now = utcnow()
        hosp_id = str(uuid4())
        insert_data = {
            "id": hosp_id,
            "name": name,
            "name_normalized": norm_name,
            "address": address,
            "location": {
                "city": city,
                "city_normalized": normalize(city),
                "state": "Tamil Nadu",
                "latitude": lat,
                "longitude": lon,
            },
            "contact": {
                "phone": phone,
                "email": f"contact@{norm_name.replace(' ', '')}.nivara.com",
                "website": f"https://{norm_name.replace(' ', '')}.nivara.com",
            },
            "appointment_intake_status": "OPEN",
            "department_ids": [],
            "created_at": now,
            "updated_at": now,
        }
        async with self.db.engine.begin() as conn:
            await conn.execute(t_hosp.insert().values(insert_data))
        self.log_created(f"Hospital '{name}'")
        return insert_data

    # ------------------------------------------------------------------ Departments
    async def ensure_department(self, hospital_id: str, name: str, description: str = "") -> dict:
        t_dept = TABLE_MAP["departments"]
        t_hosp = TABLE_MAP["hospitals"]
        norm_name = normalize(name)
        async with self.db.engine.connect() as conn:
            row = (await conn.execute(
                select(t_dept).where(and_(t_dept.c.hospital_id == hospital_id, t_dept.c.name_normalized == norm_name))
            )).mappings().first()
            if row:
                self.log_skipped(f"Department '{name}' in hospital {hospital_id} (already exists)")
                return dict(row)

        now = utcnow()
        dept_id = str(uuid4())
        insert_data = {
            "id": dept_id,
            "hospital_id": hospital_id,
            "name": name,
            "name_normalized": norm_name,
            "description": description or f"{name} department providing comprehensive clinical care.",
            "status": "ACTIVE",
            "appointment_intake_status": "OPEN",
            "created_at": now,
            "updated_at": now,
        }
        async with self.db.engine.begin() as conn:
            await conn.execute(t_dept.insert().values(insert_data))
            # Append department_id to hospital's department_ids JSON list
            hosp_row = (await conn.execute(select(t_hosp).where(t_hosp.c.id == hospital_id))).mappings().first()
            if hosp_row:
                current_depts = list(hosp_row.get("department_ids") or [])
                if dept_id not in current_depts:
                    current_depts.append(dept_id)
                    await conn.execute(
                        t_hosp.update().where(t_hosp.c.id == hospital_id).values(
                            department_ids=current_depts, updated_at=now
                        )
                    )
        self.log_created(f"Department '{name}' in hospital {hospital_id}")
        return insert_data

    # ------------------------------------------------------------------ Doctors
    async def ensure_doctor(
        self,
        name: str,
        email: str,
        specialty: str,
        hospital_id: str,
        department_id: str,
        experience: int,
        consultation_fee: float,
    ) -> dict:
        t_users = TABLE_MAP["users"]
        t_docs = TABLE_MAP["doctors"]

        async with self.db.engine.connect() as conn:
            existing_user = (await conn.execute(select(t_users).where(t_users.c.email == email))).mappings().first()
            if existing_user:
                doc_row = (await conn.execute(select(t_docs).where(t_docs.c.user_id == existing_user["id"]))).mappings().first()
                if doc_row:
                    self.log_skipped(f"Doctor {email} — {name} (already exists, leaving affiliations & status untouched)")
                    res = dict(doc_row)
                    res["user_email"] = email
                    res["user_id"] = existing_user["id"]
                    return res

        # Create new doctor with affiliations and ACTIVE/OPEN status in a single transaction
        now = utcnow()
        user_id = str(uuid4())
        doctor_id = str(uuid4())
        hashed = hash_password(PASSWORD, rounds=self.settings.bcrypt_rounds)

        user_data = {
            "id": user_id,
            "name": name,
            "email": email,
            "password_hash": hashed,
            "phone": "+91-98765-43210",
            "role": "DOCTOR",
            "is_active": True,
            "managed_hospital_ids": None,
            "created_at": now,
            "updated_at": now,
        }
        doctor_data = {
            "id": doctor_id,
            "user_id": user_id,
            "name": name,
            "specialty": specialty,
            "specialty_normalized": normalize(specialty),
            "department_ids": [department_id],
            "hospital_ids": [hospital_id],
            "experience": experience,
            "consultation_fee": consultation_fee,
            "consultation_types": ["FIRST_VISIT", "FOLLOW_UP"],
            "availability_status": "OPEN",
            "profile_status": "ACTIVE",
            "rating_sum": 0,
            "rating_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        async with self.db.engine.begin() as conn:
            await conn.execute(t_users.insert().values(user_data))
            await conn.execute(t_docs.insert().values(doctor_data))

        self.log_created(f"Doctor {email} — {name} (specialty: {specialty}, active & open)")
        doctor_data["user_email"] = email
        return doctor_data

    # ------------------------------------------------------------------ Patients
    async def ensure_patient(
        self,
        name: str,
        email: str,
        date_of_birth: str | None = None,
        gender: str = "UNDISCLOSED",
    ) -> dict:
        t_users = TABLE_MAP["users"]
        t_pats = TABLE_MAP["patients"]

        async with self.db.engine.connect() as conn:
            existing_user = (await conn.execute(select(t_users).where(t_users.c.email == email))).mappings().first()
            if existing_user:
                pat_row = (await conn.execute(select(t_pats).where(t_pats.c.user_id == existing_user["id"]))).mappings().first()
                if pat_row:
                    self.log_skipped(f"Patient {email} — {name} (already exists)")
                    res = dict(pat_row)
                    res["user_email"] = email
                    res["user_id"] = existing_user["id"]
                    res["name"] = existing_user["name"]
                    return res

        now = utcnow()
        user_id = str(uuid4())
        patient_id = str(uuid4())
        hashed = hash_password(PASSWORD, rounds=self.settings.bcrypt_rounds)

        user_data = {
            "id": user_id,
            "name": name,
            "email": email,
            "password_hash": hashed,
            "phone": "+91-91234-56789",
            "role": "PATIENT",
            "is_active": True,
            "managed_hospital_ids": None,
            "created_at": now,
            "updated_at": now,
        }
        patient_data = {
            "id": patient_id,
            "user_id": user_id,
            "date_of_birth": date_of_birth,
            "gender": gender,
            "basic_information": {},
            "created_at": now,
            "updated_at": now,
        }

        async with self.db.engine.begin() as conn:
            await conn.execute(t_users.insert().values(user_data))
            await conn.execute(t_pats.insert().values(patient_data))

        self.log_created(f"Patient {email} — {name}")
        patient_data["user_email"] = email
        patient_data["name"] = name
        return patient_data

    # ------------------------------------------------------------------ Availability & Slots
    async def ensure_availability_and_slots(
        self,
        doctor: dict,
        hospital_id: str,
        department_id: str,
        target_date: date,
        start_time: str = "09:00",
        end_time: str = "13:00",
        slot_duration: int = 30,
    ) -> dict:
        """Ensures doctor_availability and materialises 30-minute appointment_slots with exact compound key idempotency."""
        t_avail = TABLE_MAP["doctor_availability"]
        t_slots = TABLE_MAP["appointment_slots"]
        doctor_id = doctor["id"]
        date_str = target_date.isoformat()

        async with self.db.engine.connect() as conn:
            existing_avail = (await conn.execute(
                select(t_avail).where(
                    and_(
                        t_avail.c.doctor_id == doctor_id,
                        t_avail.c.hospital_id == hospital_id,
                        t_avail.c.department_id == department_id,
                        t_avail.c.date == date_str,
                        t_avail.c.start_time == start_time,
                        t_avail.c.end_time == end_time,
                    )
                )
            )).mappings().first()

        now = utcnow()
        if existing_avail:
            avail_id = existing_avail["id"]
            self.log_skipped(
                f"Availability for {doctor['name']} at {date_str} {start_time}-{end_time} (already exists)"
            )
        else:
            avail_id = str(uuid4())
            avail_data = {
                "id": avail_id,
                "doctor_id": doctor_id,
                "hospital_id": hospital_id,
                "department_id": department_id,
                "date": date_str,
                "start_time": start_time,
                "end_time": end_time,
                "slot_duration": slot_duration,
                "status": "WORKING",
                "note": "Standard development clinical hours",
                "created_at": now,
                "updated_at": now,
            }
            async with self.db.engine.begin() as conn:
                await conn.execute(t_avail.insert().values(avail_data))
            self.log_created(
                f"Availability for {doctor['name']} on {date_str} {start_time}-{end_time}"
            )

        # Generate 30-minute slots between start_time and end_time
        sh, sm = map(int, start_time.split(":"))
        eh, em = map(int, end_time.split(":"))
        start_minutes = sh * 60 + sm
        end_minutes = eh * 60 + em

        slots_created = 0
        slots_skipped = 0

        async with self.db.engine.begin() as conn:
            for cur in range(start_minutes, end_minutes, slot_duration):
                slot_st = f"{cur // 60:02d}:{cur % 60:02d}"
                nxt = cur + slot_duration
                slot_et = f"{nxt // 60:02d}:{nxt % 60:02d}"

                # Compound uniqueness check on slot
                existing_slot = (await conn.execute(
                    select(t_slots).where(
                        and_(
                            t_slots.c.doctor_id == doctor_id,
                            t_slots.c.hospital_id == hospital_id,
                            t_slots.c.department_id == department_id,
                            t_slots.c.date == date_str,
                            t_slots.c.start_time == slot_st,
                            t_slots.c.end_time == slot_et,
                        )
                    )
                )).mappings().first()

                if existing_slot:
                    slots_skipped += 1
                    continue

                slot_id = str(uuid4())
                start_at_utc = local_to_utc(date_str, slot_st, self.settings.app_timezone)
                end_at_utc = local_to_utc(date_str, slot_et, self.settings.app_timezone)

                slot_data = {
                    "id": slot_id,
                    "doctor_id": doctor_id,
                    "hospital_id": hospital_id,
                    "department_id": department_id,
                    "date": date_str,
                    "start_time": slot_st,
                    "end_time": slot_et,
                    "start_at": start_at_utc,
                    "end_at": end_at_utc,
                    "status": "AVAILABLE",
                    "appointment_id": None,
                    "held_until": None,
                    "availability_id": avail_id,
                    "block_source": None,
                    "blocked_by_availability_id": None,
                    "created_at": now,
                    "updated_at": now,
                }
                await conn.execute(t_slots.insert().values(slot_data))
                slots_created += 1

        if slots_created > 0:
            self.log_created(f"Generated {slots_created} slot(s) for {doctor['name']} on {date_str}")
        if slots_skipped > 0:
            self.log_skipped(f"Skipped {slots_skipped} existing slot(s) for {doctor['name']} on {date_str}")

        return {"availability_id": avail_id}

    # ------------------------------------------------------------------ Appointments
    async def get_available_slot(self, doctor_id: str, date_str: str) -> dict | None:
        t_slots = TABLE_MAP["appointment_slots"]
        async with self.db.engine.connect() as conn:
            stmt = select(t_slots).where(
                and_(
                    t_slots.c.doctor_id == doctor_id,
                    t_slots.c.date == date_str,
                    t_slots.c.status == "AVAILABLE",
                )
            ).order_by(t_slots.c.start_time.asc()).limit(1)
            row = (await conn.execute(stmt)).mappings().first()
            return dict(row) if row else None

    async def ensure_sample_appointment(
        self,
        patient: dict,
        doctor: dict,
        target_date: date,
        state: str,  # 'CONFIRMED', 'REQUESTED', or 'REJECTED'
        reason: str = "Routine consultation",
    ) -> None:
        """Creates sample appointments respecting the application's lifecycle:
        patient requests -> slot becomes HELD -> doctor accepts (BOOKED / CONFIRMED)
        or doctor rejects (slot returns to AVAILABLE, appt REJECTED) or left REQUESTED.
        """
        t_appts = TABLE_MAP["appointments"]
        t_slots = TABLE_MAP["appointment_slots"]
        t_hist = TABLE_MAP["appointment_history"]
        t_notif = TABLE_MAP["notifications"]

        date_str = target_date.isoformat()
        patient_id = patient["id"]
        doctor_id = doctor["id"]

        # Check if an appointment already exists for this patient, doctor, and date
        async with self.db.engine.connect() as conn:
            existing_appt = (await conn.execute(
                select(t_appts).where(
                    and_(
                        t_appts.c.patient_id == patient_id,
                        t_appts.c.doctor_id == doctor_id,
                        t_appts.c.appointment_date == date_str,
                    )
                )
            )).mappings().first()
            if existing_appt:
                self.log_skipped(
                    f"Appointment {patient['name']} <-> {doctor['name']} on {date_str} (already exists: {existing_appt['status']})"
                )
                return

        # Find an open AVAILABLE slot
        slot = await self.get_available_slot(doctor_id, date_str)
        if not slot:
            print(f"  [WARN] No available slot found for {doctor['name']} on {date_str}, skipping appointment")
            return

        slot_id = slot["id"]
        appt_id = str(uuid4())
        now = utcnow()

        # Step 1: Patient requests appointment -> slot HELD
        held_until = min(now + timedelta(minutes=self.settings.request_hold_minutes), slot["start_at"])

        appt_data = {
            "id": appt_id,
            "patient_id": patient_id,
            "patient_user_id": patient["user_id"],
            "patient_name": patient["name"],
            "doctor_id": doctor_id,
            "doctor_user_id": doctor["user_id"],
            "doctor_name": doctor["name"],
            "hospital_id": slot["hospital_id"],
            "department_id": slot["department_id"],
            "slot_id": slot_id,
            "appointment_date": date_str,
            "start_time": slot["start_time"],
            "end_time": slot["end_time"],
            "start_at": slot["start_at"],
            "end_at": slot["end_at"],
            "consultation_type": "FIRST_VISIT",
            "reason": reason,
            "status": "REQUESTED",
            "is_active": True,
            "status_reason": None,
            "reminder_sent": False,
            "created_at": now,
            "updated_at": now,
        }

        async with self.db.engine.begin() as conn:
            # Atomic transition: mark slot as HELD
            await conn.execute(
                t_slots.update().where(t_slots.c.id == slot_id).values(
                    status="HELD",
                    appointment_id=appt_id,
                    held_until=held_until,
                    updated_at=now,
                )
            )
            await conn.execute(t_appts.insert().values(appt_data))
            # History entry for creation
            await conn.execute(
                t_hist.insert().values(
                    id=str(uuid4()),
                    appointment_id=appt_id,
                    previous_status=None,
                    new_status="REQUESTED",
                    changed_by=patient["user_id"],
                    changed_by_role="PATIENT",
                    reason=reason,
                    created_at=now,
                    updated_at=now,
                )
            )

        # Step 2: Transition according to requested lifecycle state
        if state == "CONFIRMED":
            now_decision = utcnow()
            async with self.db.engine.begin() as conn:
                # Slot promoted to BOOKED
                await conn.execute(
                    t_slots.update().where(t_slots.c.id == slot_id).values(
                        status="BOOKED",
                        held_until=None,
                        updated_at=now_decision,
                    )
                )
                # Appointment promoted to CONFIRMED
                await conn.execute(
                    t_appts.update().where(t_appts.c.id == appt_id).values(
                        status="CONFIRMED",
                        is_active=True,
                        updated_at=now_decision,
                    )
                )
                # Audit history
                await conn.execute(
                    t_hist.insert().values(
                        id=str(uuid4()),
                        appointment_id=appt_id,
                        previous_status="REQUESTED",
                        new_status="CONFIRMED",
                        changed_by=doctor["user_id"],
                        changed_by_role="DOCTOR",
                        reason="Confirmed by doctor",
                        created_at=now_decision,
                        updated_at=now_decision,
                    )
                )
                # Notification to patient
                await conn.execute(
                    t_notif.insert().values(
                        id=str(uuid4()),
                        user_id=patient["user_id"],
                        type="APPOINTMENT_ACCEPTED",
                        title="Appointment confirmed",
                        message=f"Dr. {doctor['name']} confirmed your appointment on {date_str} at {slot['start_time']}.",
                        related_appointment_id=appt_id,
                        is_read=False,
                        data={},
                        created_at=now_decision,
                        updated_at=now_decision,
                    )
                )
            self.log_created(
                f"Appointment {patient['name']} <-> {doctor['name']} on {date_str} (CONFIRMED, slot BOOKED)"
            )

        elif state == "REJECTED":
            now_decision = utcnow()
            reject_reason = "Doctor unavailable due to emergency duty"
            async with self.db.engine.begin() as conn:
                # Slot released back to AVAILABLE
                await conn.execute(
                    t_slots.update().where(t_slots.c.id == slot_id).values(
                        status="AVAILABLE",
                        appointment_id=None,
                        held_until=None,
                        updated_at=now_decision,
                    )
                )
                # Appointment updated to REJECTED
                await conn.execute(
                    t_appts.update().where(t_appts.c.id == appt_id).values(
                        status="REJECTED",
                        is_active=False,
                        status_reason=reject_reason,
                        updated_at=now_decision,
                    )
                )
                # Audit history
                await conn.execute(
                    t_hist.insert().values(
                        id=str(uuid4()),
                        appointment_id=appt_id,
                        previous_status="REQUESTED",
                        new_status="REJECTED",
                        changed_by=doctor["user_id"],
                        changed_by_role="DOCTOR",
                        reason=reject_reason,
                        created_at=now_decision,
                        updated_at=now_decision,
                    )
                )
                # Notification to patient
                await conn.execute(
                    t_notif.insert().values(
                        id=str(uuid4()),
                        user_id=patient["user_id"],
                        type="APPOINTMENT_REJECTED",
                        title="Appointment request declined",
                        message=f"Dr. {doctor['name']} could not accept your request for {date_str}. Reason: {reject_reason}",
                        related_appointment_id=appt_id,
                        is_read=False,
                        data={},
                        created_at=now_decision,
                        updated_at=now_decision,
                    )
                )
            self.log_created(
                f"Appointment {patient['name']} <-> {doctor['name']} on {date_str} (REJECTED, slot released to AVAILABLE)"
            )

        elif state == "REQUESTED":
            # Left in REQUESTED state with slot HELD
            self.log_created(
                f"Appointment {patient['name']} <-> {doctor['name']} on {date_str} (REQUESTED, slot HELD)"
            )


# ---------------------------------------------------------------------- Preflight
async def run_preflight(db, settings, allow_production_override: bool = False) -> None:
    print("=" * 60)
    print("NIVARA SUPABASE SEED — DATABASE PREFLIGHT")
    print("=" * 60)

    # 1. Environment Safety Check
    env = settings.environment
    print(f"[*] Environment configured: '{env}'")
    if env != "development" and not allow_production_override:
        print(
            f"\n[ERROR] Refusing to seed environment '{env}'.\n"
            "This script is for development seeding only.\n"
            "If you intentionally want to run this against this environment, pass:\n"
            "    python scripts/seed_supabase.py --allow-production-seed\n",
            file=sys.stderr,
        )
        sys.exit(1)
    elif env != "development" and allow_production_override:
        print("  [!] WARNING: Production environment override active (--allow-production-seed)")

    # 2. Database URL presence
    url = settings.database_url
    if not url:
        print("[ERROR] DATABASE_URL is not configured.", file=sys.stderr)
        sys.exit(1)
    redacted = url.split("@")[-1] if "@" in url else url[:20] + "..."
    print(f"[*] Database host/target: {redacted}")

    # 3. Connection Check
    try:
        async with db.engine.connect() as conn:
            res = await conn.execute(select(1))
            assert res.scalar() == 1
        print("[*] PostgreSQL connection: SUCCESS (SELECT 1 passed)")
    except Exception as exc:
        print(f"[ERROR] Failed to connect to PostgreSQL: {exc}", file=sys.stderr)
        sys.exit(1)

    # 4. Check all 15 required Nivara tables exist
    missing_tables = []
    async with db.engine.connect() as conn:
        for tname in REQUIRED_TABLES:
            try:
                table = TABLE_MAP[tname]
                await conn.execute(select(func.count()).select_from(table))
            except Exception:
                missing_tables.append(tname)

    if missing_tables:
        print(f"[ERROR] Missing required Nivara tables: {missing_tables}", file=sys.stderr)
        sys.exit(1)
    print(f"[*] All {len(REQUIRED_TABLES)} required Nivara PostgreSQL tables verified: OK")

    # 5. Check real patient account baseline
    t_users = TABLE_MAP["users"]
    async with db.engine.connect() as conn:
        real_user = (await conn.execute(select(t_users).where(t_users.c.email == PRESERVED_PATIENT_EMAIL))).mappings().first()
        if real_user:
            print(f"[*] Preserved patient account check: '{PRESERVED_PATIENT_EMAIL}' found (role: {real_user['role']}) — SAFE")
        else:
            print(f"[*] Preserved patient account check: '{PRESERVED_PATIENT_EMAIL}' not present — SAFE")

    print("[*] Preflight validation passed successfully!\n")


# ---------------------------------------------------------------------- Main
async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Supabase PostgreSQL with Nivara development data.")
    parser.add_argument(
        "--allow-production-seed",
        action="store_true",
        help="Explicit override to allow running against a non-development environment.",
    )
    args = parser.parse_args()

    settings = get_settings()
    manager = DatabaseManager(settings)
    db = await manager.connect()

    try:
        # 1. Run Preflight
        await run_preflight(db, settings, allow_production_override=args.allow_production_seed)

        # 2. Seeder execution
        print("=" * 60)
        print("SEEDING NIVARA DEVELOPMENT DATA")
        print("=" * 60)
        s = Seeder(db, settings)

        # A. Admin
        print("\n--- 1. Platform Admin ---")
        admin = await s.ensure_admin()

        # B. Hospitals
        print("\n--- 2. Hospitals ---")
        h1 = await s.ensure_hospital(
            name="City General Hospital",
            city="Chennai",
            lat=13.0827,
            lon=80.2707,
            address="1 City General Hospital Road, Chennai",
            phone="+91-44-2530-0000",
        )
        h2 = await s.ensure_hospital(
            name="Lakeside Multispecialty Clinic",
            city="Tiruchirappalli",
            lat=10.7905,
            lon=78.7047,
            address="2 Lakeside Clinic Road, Tiruchirappalli",
            phone="+91-431-270-0000",
        )

        # C. Departments
        print("\n--- 3. Departments ---")
        d_h1_gen = await s.ensure_department(h1["id"], "General Medicine")
        d_h1_card = await s.ensure_department(h1["id"], "Cardiology")
        d_h1_derm = await s.ensure_department(h1["id"], "Dermatology")

        d_h2_gen = await s.ensure_department(h2["id"], "General Medicine")
        d_h2_orth = await s.ensure_department(h2["id"], "Orthopedics")

        # D. Doctors
        print("\n--- 4. Doctors ---")
        doctors = [
            await s.ensure_doctor(
                name="Dr. Asha Rao",
                email="doctor1@nivara.com",
                specialty="General Medicine",
                hospital_id=h1["id"],
                department_id=d_h1_gen["id"],
                experience=10,
                consultation_fee=300.0,
            ),
            await s.ensure_doctor(
                name="Dr. Ravi Kumar",
                email="doctor2@nivara.com",
                specialty="Cardiology",
                hospital_id=h1["id"],
                department_id=d_h1_card["id"],
                experience=15,
                consultation_fee=800.0,
            ),
            await s.ensure_doctor(
                name="Dr. Meena Iyer",
                email="doctor3@nivara.com",
                specialty="Dermatology",
                hospital_id=h1["id"],
                department_id=d_h1_derm["id"],
                experience=6,
                consultation_fee=500.0,
            ),
            await s.ensure_doctor(
                name="Dr. Suresh Babu",
                email="doctor4@nivara.com",
                specialty="General Medicine",
                hospital_id=h2["id"],
                department_id=d_h2_gen["id"],
                experience=4,
                consultation_fee=250.0,
            ),
            await s.ensure_doctor(
                name="Dr. Priya Nathan",
                email="doctor5@nivara.com",
                specialty="Orthopedics",
                hospital_id=h2["id"],
                department_id=d_h2_orth["id"],
                experience=8,
                consultation_fee=600.0,
            ),
        ]

        # E. Patients
        print("\n--- 5. Patients ---")
        patients = [
            await s.ensure_patient("Test Patient One", "patient1@nivara.com", date_of_birth="1990-05-01", gender="FEMALE"),
            await s.ensure_patient("Test Patient Two", "patient2@nivara.com", date_of_birth="1985-11-20", gender="MALE"),
            await s.ensure_patient("Test Patient Three", "patient3@nivara.com"),
            await s.ensure_patient("Test Patient Four", "patient4@nivara.com"),
            await s.ensure_patient("Test Patient Five", "patient5@nivara.com"),
        ]

        # F. Doctor Availability & Slots (Upcoming 3 Days)
        print("\n--- 6. Doctor Availability & Slots ---")
        today = today_local(settings.app_timezone)
        future_days = [today + timedelta(days=1), today + timedelta(days=2), today + timedelta(days=3)]

        # Map doctors to their hospital and department
        doc_affiliations = [
            (doctors[0], h1["id"], d_h1_gen["id"]),
            (doctors[1], h1["id"], d_h1_card["id"]),
            (doctors[2], h1["id"], d_h1_derm["id"]),
            (doctors[3], h2["id"], d_h2_gen["id"]),
            (doctors[4], h2["id"], d_h2_orth["id"]),
        ]

        for doc, hosp_id, dept_id in doc_affiliations:
            for day in future_days:
                await s.ensure_availability_and_slots(
                    doctor=doc,
                    hospital_id=hosp_id,
                    department_id=dept_id,
                    target_date=day,
                    start_time="09:00",
                    end_time="13:00",
                    slot_duration=30,
                )

        # G. Sample Appointments (Different Lifecycle States)
        print("\n--- 7. Sample Appointments ---")
        # 1. CONFIRMED: Patient 1 <-> Dr. Asha Rao on Day 1
        await s.ensure_sample_appointment(patients[0], doctors[0], future_days[0], state="CONFIRMED", reason="Routine follow-up")
        # 2. REQUESTED: Patient 2 <-> Dr. Asha Rao on Day 1
        await s.ensure_sample_appointment(patients[1], doctors[0], future_days[0], state="REQUESTED", reason="Persistent headache")
        # 3. CONFIRMED: Patient 3 <-> Dr. Ravi Kumar on Day 2
        await s.ensure_sample_appointment(patients[2], doctors[1], future_days[1], state="CONFIRMED", reason="Cardiac health review")
        # 4. REJECTED: Patient 4 <-> Dr. Meena Iyer on Day 2
        await s.ensure_sample_appointment(patients[3], doctors[2], future_days[1], state="REJECTED", reason="Skin rash evaluation")
        # 5. REQUESTED: Patient 5 <-> Dr. Suresh Babu on Day 3
        await s.ensure_sample_appointment(patients[4], doctors[3], future_days[2], state="REQUESTED", reason="General health checkup")

        # 3. Post-Seed Table Summary & Integrity Check
        print("\n" + "=" * 60)
        print("DATABASE RECORD COUNTS AFTER SEED")
        print("=" * 60)
        async with db.engine.connect() as conn:
            for tname in [
                "users",
                "patients",
                "doctors",
                "hospitals",
                "departments",
                "doctor_availability",
                "appointment_slots",
                "appointments",
                "appointment_history",
                "notifications",
            ]:
                table = TABLE_MAP[tname]
                count = (await conn.execute(select(func.count()).select_from(table))).scalar()
                print(f"  {tname.ljust(24)}: {count}")

        # Confirm preserved patient still exists and was not altered
        async with db.engine.connect() as conn:
            t_users = TABLE_MAP["users"]
            real_patient = (await conn.execute(select(t_users).where(t_users.c.email == PRESERVED_PATIENT_EMAIL))).mappings().first()
            print("\nPreserved Patient Check:")
            if real_patient:
                print(f"  [OK] '{PRESERVED_PATIENT_EMAIL}' intact: id={real_patient['id']}, role={real_patient['role']}, active={real_patient['is_active']}")
            else:
                print(f"  [NOTE] '{PRESERVED_PATIENT_EMAIL}' was not present initially.")

        print("\nSeeding Complete Summary:")
        print(f"  Total items created: {len(s.created)}")
        print(f"  Total items skipped: {len(s.skipped)}")
        print("\nAll seeded accounts use password: " + PASSWORD)

    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
