"""SQLAlchemy 2.0 table definitions for Nivara PostgreSQL schema.

Covers all 15 entities:
1. users
2. patients
3. doctors
4. hospitals
5. departments
6. doctor_availability
7. appointment_slots
8. appointments
9. appointment_history
10. medical_records
11. reviews
12. notifications
13. waitlist_entries
14. symptom_routing_rules
15. intake_events
"""
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
)

metadata = MetaData()

# 1. users
users_table = Table(
    "users",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("email", String(255), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("phone", String(50), nullable=True),
    Column("role", String(20), nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("managed_hospital_ids", JSON, nullable=True),  # list[str] | None
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_users_role_active", "role", "is_active"),
    CheckConstraint("role IN ('PATIENT', 'DOCTOR', 'ADMIN')", name="ck_users_role"),
)

# 2. patients
patients_table = Table(
    "patients",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("date_of_birth", String(10), nullable=True),
    Column("gender", String(20), nullable=False, default="UNDISCLOSED"),
    Column("basic_information", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("gender IN ('MALE', 'FEMALE', 'OTHER', 'UNDISCLOSED')", name="ck_patients_gender"),
)

# 3. hospitals
hospitals_table = Table(
    "hospitals",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("name_normalized", String(255), nullable=False),
    Column("address", Text, nullable=False),
    Column("location", JSON, nullable=False, default=dict),  # {city, state, latitude, longitude, city_normalized}
    Column("contact", JSON, nullable=False, default=dict),  # {phone, email, website}
    Column("appointment_intake_status", String(20), nullable=False, default="OPEN"),
    Column("department_ids", JSON, nullable=False, default=list),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_hospitals_name", "name_normalized"),
    Index("ix_hospitals_intake", "appointment_intake_status"),
    CheckConstraint("appointment_intake_status IN ('OPEN', 'CLOSED')", name="ck_hospitals_intake"),
)

# 4. departments
departments_table = Table(
    "departments",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("hospital_id", Uuid(as_uuid=False), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("name_normalized", String(255), nullable=False),
    Column("description", Text, nullable=True),
    Column("status", String(20), nullable=False, default="ACTIVE"),
    Column("appointment_intake_status", String(20), nullable=False, default="OPEN"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("uq_departments_hospital_name", "hospital_id", "name_normalized", unique=True),
    Index("ix_departments_name", "name_normalized"),
    CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_departments_status"),
    CheckConstraint("appointment_intake_status IN ('OPEN', 'CLOSED')", name="ck_departments_intake"),
)

# 5. doctors
doctors_table = Table(
    "doctors",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("name", String(255), nullable=False),
    Column("specialty", String(255), nullable=False),
    Column("specialty_normalized", String(255), nullable=False),
    Column("department_ids", JSON, nullable=False, default=list),
    Column("hospital_ids", JSON, nullable=False, default=list),
    Column("experience", Integer, nullable=False, default=0),
    Column("consultation_fee", Float, nullable=False, default=0.0),
    Column("consultation_types", JSON, nullable=False, default=list),
    Column("availability_status", String(20), nullable=False, default="OPEN"),
    Column("profile_status", String(20), nullable=False, default="PENDING"),
    Column("rating_sum", Integer, nullable=False, default=0),
    Column("rating_count", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_doctors_specialty", "specialty_normalized"),
    Index("ix_doctors_status", "profile_status", "availability_status"),
    CheckConstraint("availability_status IN ('OPEN', 'CLOSED')", name="ck_doctors_availability_status"),
    CheckConstraint("profile_status IN ('PENDING', 'ACTIVE', 'SUSPENDED')", name="ck_doctors_profile_status"),
)

# 6. doctor_availability
doctor_availability_table = Table(
    "doctor_availability",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("doctor_id", Uuid(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
    Column("hospital_id", Uuid(as_uuid=False), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
    Column("department_id", Uuid(as_uuid=False), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False),
    Column("date", String(10), nullable=False),
    Column("start_time", String(5), nullable=False),
    Column("end_time", String(5), nullable=False),
    Column("slot_duration", Integer, nullable=False, default=30),
    Column("status", String(20), nullable=False, default="WORKING"),
    Column("note", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_availability_doctor_date", "doctor_id", "date"),
    CheckConstraint("status IN ('WORKING', 'BLOCKED')", name="ck_doctor_availability_status"),
)

# 7. appointment_slots
appointment_slots_table = Table(
    "appointment_slots",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("doctor_id", Uuid(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
    Column("hospital_id", Uuid(as_uuid=False), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
    Column("department_id", Uuid(as_uuid=False), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False),
    Column("date", String(10), nullable=False),
    Column("start_time", String(5), nullable=False),
    Column("end_time", String(5), nullable=False),
    Column("start_at", DateTime(timezone=False), nullable=False),
    Column("end_at", DateTime(timezone=False), nullable=False),
    Column("status", String(20), nullable=False, default="AVAILABLE"),
    Column("appointment_id", Uuid(as_uuid=False), nullable=True),
    Column("held_until", DateTime(timezone=False), nullable=True),
    Column("availability_id", Uuid(as_uuid=False), ForeignKey("doctor_availability.id", ondelete="CASCADE"), nullable=True),
    Column("block_source", String(50), nullable=True),
    Column("blocked_by_availability_id", Uuid(as_uuid=False), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("uq_slots_doctor_date_start", "doctor_id", "date", "start_time", unique=True),
    Index("ix_slots_doctor_date_status", "doctor_id", "date", "status"),
    Index("ix_slots_status_held_until", "status", "held_until"),
    Index("ix_slots_facility_status_start", "hospital_id", "department_id", "status", "start_at"),
    Index("ix_slots_availability", "availability_id"),
    Index("ix_slots_appointment", "appointment_id"),
    CheckConstraint("status IN ('AVAILABLE', 'HELD', 'BOOKED', 'BLOCKED')", name="ck_slots_status"),
)

# 8. appointments
appointments_table = Table(
    "appointments",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("patient_id", Uuid(as_uuid=False), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
    Column("patient_user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("patient_name", String(255), nullable=False),
    Column("doctor_id", Uuid(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
    Column("doctor_user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("doctor_name", String(255), nullable=False),
    Column("hospital_id", Uuid(as_uuid=False), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
    Column("department_id", Uuid(as_uuid=False), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False),
    Column("slot_id", Uuid(as_uuid=False), ForeignKey("appointment_slots.id", ondelete="CASCADE"), nullable=False),
    Column("appointment_date", String(10), nullable=False),
    Column("start_time", String(5), nullable=False),
    Column("end_time", String(5), nullable=False),
    Column("start_at", DateTime(timezone=False), nullable=False),
    Column("end_at", DateTime(timezone=False), nullable=False),
    Column("consultation_type", String(50), nullable=False),
    Column("reason", Text, nullable=True),
    Column("status", String(20), nullable=False, default="REQUESTED"),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("status_reason", Text, nullable=True),
    Column("reminder_sent", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_appointments_slot", "slot_id"),
    Index("ix_appointments_doctor_status", "doctor_id", "status", "start_at"),
    Index("ix_appointments_patient_status", "patient_id", "status", "start_at"),
    Index("ix_appointments_date", "appointment_date"),
    Index("ix_appointments_status_start", "status", "start_at"),
    CheckConstraint("status IN ('REQUESTED', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'COMPLETED', 'NO_SHOW')", name="ck_appointments_status"),
)

# 9. appointment_history
appointment_history_table = Table(
    "appointment_history",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("appointment_id", Uuid(as_uuid=False), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
    Column("previous_status", String(50), nullable=True),
    Column("new_status", String(50), nullable=False),
    Column("changed_by", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("changed_by_role", String(50), nullable=False),
    Column("reason", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_history_appointment", "appointment_id", "created_at"),
)

# 10. medical_records
medical_records_table = Table(
    "medical_records",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("patient_id", Uuid(as_uuid=False), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
    Column("doctor_id", Uuid(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
    Column("appointment_id", Uuid(as_uuid=False), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("notes", Text, nullable=False),
    Column("documents", JSON, nullable=False, default=list),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_records_patient", "patient_id", "created_at"),
    Index("ix_records_doctor", "doctor_id", "created_at"),
)

# 11. reviews
reviews_table = Table(
    "reviews",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("patient_id", Uuid(as_uuid=False), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
    Column("doctor_id", Uuid(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
    Column("appointment_id", Uuid(as_uuid=False), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("rating", Integer, nullable=False),
    Column("comment", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_reviews_doctor", "doctor_id", "created_at"),
    Index("ix_reviews_patient", "patient_id"),
    CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating"),
)

# 12. notifications
notifications_table = Table(
    "notifications",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("type", String(50), nullable=False),
    Column("title", String(255), nullable=False),
    Column("message", Text, nullable=False),
    Column("related_appointment_id", Uuid(as_uuid=False), nullable=True),
    Column("is_read", Boolean, nullable=False, default=False),
    Column("data", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_notifications_user", "user_id", "is_read", "created_at"),
)

# 13. waitlist_entries
waitlist_entries_table = Table(
    "waitlist_entries",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("patient_id", Uuid(as_uuid=False), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
    Column("patient_user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("doctor_id", Uuid(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=True),
    Column("department_id", Uuid(as_uuid=False), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True),
    Column("hospital_id", Uuid(as_uuid=False), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True),
    Column("specialty", String(255), nullable=True),
    Column("specialty_normalized", String(255), nullable=True),
    Column("date_from", String(10), nullable=False),
    Column("date_to", String(10), nullable=False),
    Column("time_from", String(5), nullable=True),
    Column("time_to", String(5), nullable=True),
    Column("consultation_type", String(50), nullable=True),
    Column("existing_appointment_id", Uuid(as_uuid=False), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
    Column("status", String(20), nullable=False, default="ACTIVE"),
    Column("notified_slot_ids", JSON, nullable=False, default=list),
    Column("fulfilled_appointment_id", Uuid(as_uuid=False), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_waitlist_doctor", "doctor_id"),
    Index("ix_waitlist_department", "department_id"),
    Index("ix_waitlist_hospital", "hospital_id"),
    Index("ix_waitlist_status_dates", "status", "date_from", "date_to"),
    Index("ix_waitlist_patient", "patient_id", "status"),
    CheckConstraint("status IN ('ACTIVE', 'FULFILLED', 'CANCELLED', 'EXPIRED')", name="ck_waitlist_status"),
)

# 14. symptom_routing_rules
symptom_routing_rules_table = Table(
    "symptom_routing_rules",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("department_name", String(255), nullable=False),
    Column("department_name_normalized", String(255), nullable=False),
    Column("keywords", JSON, nullable=False, default=list),
    Column("weight", Float, nullable=False, default=1.0),
    Column("is_emergency", Boolean, nullable=False, default=False),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_rules_department", "department_name_normalized"),
)

# 15. intake_events
intake_events_table = Table(
    "intake_events",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("target_type", String(50), nullable=False),
    Column("target_id", Uuid(as_uuid=False), nullable=False),
    Column("hospital_id", Uuid(as_uuid=False), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
    Column("previous_status", String(20), nullable=False),
    Column("new_status", String(20), nullable=False),
    Column("changed_by", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("reason", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_intake_events_target", "target_type", "target_id", "created_at"),
)

TABLE_MAP: dict[str, Table] = {
    "users": users_table,
    "patients": patients_table,
    "doctors": doctors_table,
    "hospitals": hospitals_table,
    "departments": departments_table,
    "doctor_availability": doctor_availability_table,
    "appointment_slots": appointment_slots_table,
    "appointments": appointments_table,
    "appointment_history": appointment_history_table,
    "medical_records": medical_records_table,
    "reviews": reviews_table,
    "notifications": notifications_table,
    "waitlist_entries": waitlist_entries_table,
    "symptom_routing_rules": symptom_routing_rules_table,
    "intake_events": intake_events_table,
}
