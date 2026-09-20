"""Index definitions. Idempotent — safe to run on every startup.

Concurrency-critical indexes (see README "Slot conflict strategy"):

* ``appointment_slots (doctor_id, date, start_time)`` UNIQUE — a doctor can never have
  two slot documents for the same time, so schedule generation is idempotent.
* ``appointments (slot_id)`` UNIQUE where ``is_active`` — second line of defence: even if
  application logic were bypassed, only ONE active (REQUESTED/CONFIRMED) appointment can
  reference a slot.
* ``appointments (patient_id, start_at)`` UNIQUE where ``is_active`` — a patient cannot hold
  two active appointments that start at the same instant.

The first line of defence is the atomic conditional slot update in ``SlotService``.
"""
import logging
from typing import Any

from pymongo import ASCENDING, DESCENDING, GEOSPHERE  # noqa: F401  (GEOSPHERE kept for future use)

from app.database.collections import C

logger = logging.getLogger("smartcare.db")

ACTIVE_PARTIAL = {"is_active": True}


async def ensure_indexes(db: Any) -> None:
    # users / profiles
    await db[C.USERS].create_index([("email", ASCENDING)], unique=True, name="uq_users_email")
    await db[C.USERS].create_index([("role", ASCENDING), ("is_active", ASCENDING)], name="ix_users_role_active")

    await db[C.PATIENTS].create_index([("user_id", ASCENDING)], unique=True, name="uq_patients_user")

    d = db[C.DOCTORS]
    await d.create_index([("user_id", ASCENDING)], unique=True, name="uq_doctors_user")
    await d.create_index([("specialty_normalized", ASCENDING)], name="ix_doctors_specialty")
    await d.create_index([("department_ids", ASCENDING)], name="ix_doctors_departments")
    await d.create_index([("hospital_ids", ASCENDING)], name="ix_doctors_hospitals")
    await d.create_index(
        [("profile_status", ASCENDING), ("availability_status", ASCENDING)], name="ix_doctors_status"
    )
    await d.create_index([("consultation_types", ASCENDING)], name="ix_doctors_consultation_types")

    # facilities
    h = db[C.HOSPITALS]
    await h.create_index([("name_normalized", ASCENDING)], name="ix_hospitals_name")
    await h.create_index([("location.city_normalized", ASCENDING)], name="ix_hospitals_city")
    await h.create_index([("appointment_intake_status", ASCENDING)], name="ix_hospitals_intake")

    dep = db[C.DEPARTMENTS]
    await dep.create_index(
        [("hospital_id", ASCENDING), ("name_normalized", ASCENDING)], unique=True, name="uq_departments_hospital_name"
    )
    await dep.create_index([("name_normalized", ASCENDING)], name="ix_departments_name")

    # scheduling
    await db[C.DOCTOR_AVAILABILITY].create_index(
        [("doctor_id", ASCENDING), ("date", ASCENDING)], name="ix_availability_doctor_date"
    )

    s = db[C.APPOINTMENT_SLOTS]
    await s.create_index(
        [("doctor_id", ASCENDING), ("date", ASCENDING), ("start_time", ASCENDING)],
        unique=True,
        name="uq_slots_doctor_date_start",
    )
    await s.create_index(
        [("doctor_id", ASCENDING), ("date", ASCENDING), ("status", ASCENDING)], name="ix_slots_doctor_date_status"
    )
    await s.create_index([("status", ASCENDING), ("held_until", ASCENDING)], name="ix_slots_status_held_until")
    await s.create_index(
        [("hospital_id", ASCENDING), ("department_id", ASCENDING), ("status", ASCENDING), ("start_at", ASCENDING)],
        name="ix_slots_facility_status_start",
    )
    await s.create_index([("availability_id", ASCENDING)], name="ix_slots_availability")
    await s.create_index([("appointment_id", ASCENDING)], name="ix_slots_appointment", sparse=True)

    a = db[C.APPOINTMENTS]
    await a.create_index(
        [("slot_id", ASCENDING)],
        unique=True,
        partialFilterExpression=ACTIVE_PARTIAL,
        name="uq_appointments_active_slot",
    )
    await a.create_index(
        [("patient_id", ASCENDING), ("start_at", ASCENDING)],
        unique=True,
        partialFilterExpression=ACTIVE_PARTIAL,
        name="uq_appointments_active_patient_start",
    )
    await a.create_index([("slot_id", ASCENDING)], name="ix_appointments_slot")
    await a.create_index(
        [("doctor_id", ASCENDING), ("status", ASCENDING), ("start_at", ASCENDING)], name="ix_appointments_doctor_status"
    )
    await a.create_index(
        [("patient_id", ASCENDING), ("status", ASCENDING), ("start_at", ASCENDING)], name="ix_appointments_patient_status"
    )
    await a.create_index([("appointment_date", ASCENDING)], name="ix_appointments_date")
    await a.create_index([("status", ASCENDING), ("start_at", ASCENDING)], name="ix_appointments_status_start")

    await db[C.APPOINTMENT_HISTORY].create_index(
        [("appointment_id", ASCENDING), ("created_at", ASCENDING)], name="ix_history_appointment"
    )

    # clinical
    mr = db[C.MEDICAL_RECORDS]
    await mr.create_index([("appointment_id", ASCENDING)], unique=True, name="uq_records_appointment")
    await mr.create_index([("patient_id", ASCENDING), ("created_at", DESCENDING)], name="ix_records_patient")
    await mr.create_index([("doctor_id", ASCENDING), ("created_at", DESCENDING)], name="ix_records_doctor")

    r = db[C.REVIEWS]
    await r.create_index([("appointment_id", ASCENDING)], unique=True, name="uq_reviews_appointment")
    await r.create_index([("doctor_id", ASCENDING), ("created_at", DESCENDING)], name="ix_reviews_doctor")
    await r.create_index([("patient_id", ASCENDING)], name="ix_reviews_patient")

    # engagement
    await db[C.NOTIFICATIONS].create_index(
        [("user_id", ASCENDING), ("is_read", ASCENDING), ("created_at", DESCENDING)], name="ix_notifications_user"
    )

    w = db[C.WAITLIST_ENTRIES]
    await w.create_index([("doctor_id", ASCENDING)], name="ix_waitlist_doctor")
    await w.create_index([("department_id", ASCENDING)], name="ix_waitlist_department")
    await w.create_index([("hospital_id", ASCENDING)], name="ix_waitlist_hospital")
    await w.create_index(
        [("status", ASCENDING), ("date_from", ASCENDING), ("date_to", ASCENDING)], name="ix_waitlist_status_dates"
    )
    await w.create_index([("patient_id", ASCENDING), ("status", ASCENDING)], name="ix_waitlist_patient")

    await db[C.SYMPTOM_ROUTING_RULES].create_index(
        [("department_name_normalized", ASCENDING)], name="ix_rules_department"
    )
    await db[C.INTAKE_EVENTS].create_index(
        [("target_type", ASCENDING), ("target_id", ASCENDING), ("created_at", DESCENDING)], name="ix_intake_events_target"
    )
    logger.info("MongoDB indexes ensured")
