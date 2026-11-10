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
    BigInteger,
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
    text,
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
    Index("ix_patients_created_at", "created_at"),
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
    Column("waitlist_offer_id", Uuid(as_uuid=False), ForeignKey("waitlist_offers.id", ondelete="SET NULL", use_alter=True, name="fk_appointment_slots_waitlist_offer"), nullable=True),
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
    Index("ix_slots_waitlist_offer", "waitlist_offer_id"),
    Index("ix_slots_hospital_date_status", "hospital_id", "date", "status"),
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
    Index("ix_appointments_hospital_date_status", "hospital_id", "appointment_date", "status"),
    Index("ix_appointments_department_date_status", "department_id", "appointment_date", "status"),
    CheckConstraint("status IN ('REQUESTED', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', 'RESCHEDULE_REQUESTED')", name="ck_appointments_status"),
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
    Column("previous_date", String(10), nullable=True),
    Column("previous_time", String(5), nullable=True),
    Column("new_date", String(10), nullable=True),
    Column("new_time", String(5), nullable=True),
    Column("metadata", JSON, nullable=True),
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
    Column("category", String(50), nullable=False, default="APPOINTMENT"),
    Column("action_url", String(500), nullable=True),
    Column("related_appointment_id", Uuid(as_uuid=False), nullable=True),
    Column("is_read", Boolean, nullable=False, default=False),
    Column("read_at", DateTime(timezone=True), nullable=True),
    Column("data", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_notifications_user", "user_id", "is_read", "created_at"),
    Index("ix_notifications_user_category", "user_id", "category", "created_at"),
)

# 12b. notification_preferences
notification_preferences_table = Table(
    "notification_preferences",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("category", String(50), nullable=False),
    Column("enabled", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_notification_preferences_user", "user_id"),
    Index("uq_notification_preferences_user_category", "user_id", "category", unique=True),
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

# 13b. waitlist_offers
waitlist_offers_table = Table(
    "waitlist_offers",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("waitlist_entry_id", Uuid(as_uuid=False), ForeignKey("waitlist_entries.id", ondelete="CASCADE"), nullable=False),
    Column("patient_id", Uuid(as_uuid=False), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
    Column("doctor_id", Uuid(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
    Column("slot_id", Uuid(as_uuid=False), ForeignKey("appointment_slots.id", ondelete="SET NULL"), nullable=True),
    Column("status", String(20), nullable=False, default="PENDING"),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("responded_at", DateTime(timezone=True), nullable=True),
    Column("reason", Text, nullable=True),
    Column("appointment_id", Uuid(as_uuid=False), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("uq_waitlist_offers_pending_slot", "slot_id", unique=True, postgresql_where=text("status = 'PENDING'")),
    Index("ix_waitlist_offers_patient", "patient_id", "status"),
    Index("ix_waitlist_offers_entry", "waitlist_entry_id"),
    Index("ix_waitlist_offers_doctor", "doctor_id", "status"),
    Index("ix_waitlist_offers_status_expires", "status", "expires_at"),
    CheckConstraint("status IN ('PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'CANCELLED')", name="ck_waitlist_offers_status"),
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

# 16. rescheduling_requests
rescheduling_requests_table = Table(
    "rescheduling_requests",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("appointment_id", Uuid(as_uuid=False), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
    Column("patient_id", Uuid(as_uuid=False), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
    Column("patient_user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("patient_name", String(255), nullable=True),
    Column("doctor_id", Uuid(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
    Column("doctor_user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("doctor_name", String(255), nullable=True),
    Column("hospital_id", Uuid(as_uuid=False), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
    Column("department_id", Uuid(as_uuid=False), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False),
    Column("old_slot_id", Uuid(as_uuid=False), ForeignKey("appointment_slots.id", ondelete="CASCADE"), nullable=False),
    Column("requested_slot_id", Uuid(as_uuid=False), ForeignKey("appointment_slots.id", ondelete="CASCADE"), nullable=False),
    Column("old_appointment_date", String(10), nullable=True),
    Column("old_start_time", String(5), nullable=True),
    Column("old_end_time", String(5), nullable=True),
    Column("requested_appointment_date", String(10), nullable=True),
    Column("requested_start_time", String(5), nullable=True),
    Column("requested_end_time", String(5), nullable=True),
    Column("reason", Text, nullable=False),
    Column("status", String(20), nullable=False, default="REQUESTED"),
    Column("doctor_response", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("resolved_at", DateTime(timezone=True), nullable=True),
    Index("ix_reschedule_appointment", "appointment_id"),
    Index("ix_reschedule_patient_status", "patient_id", "status"),
    Index("ix_reschedule_doctor_status", "doctor_id", "status"),
    Index("uq_reschedule_active_appointment", "appointment_id", unique=True, postgresql_where=text("status = 'REQUESTED'")),
    CheckConstraint("status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'CANCELLED')", name="ck_rescheduling_requests_status"),
)

# 17. medical_documents
medical_documents_table = Table(
    "medical_documents",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("patient_id", Uuid(as_uuid=False), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
    Column("patient_user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("title", String(255), nullable=False),
    Column("category", String(50), nullable=False),
    Column("description", Text, nullable=True),
    Column("filename", String(255), nullable=False),
    Column("file_type", String(100), nullable=False),
    Column("file_size", BigInteger, nullable=False),
    Column("storage_path", String(500), nullable=False),
    Column("storage_provider", String(50), nullable=False, default="LOCAL"),
    Column("appointment_id", Uuid(as_uuid=False), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
    Column("is_deleted", Boolean, nullable=False, default=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_medical_documents_patient", "patient_id", "is_deleted", "created_at"),
    Index("ix_medical_documents_category", "category"),
    Index("ix_medical_documents_appointment", "appointment_id"),
    CheckConstraint("category IN ('LAB_REPORT', 'PRESCRIPTION', 'IMAGING', 'DISCHARGE_SUMMARY', 'CONSULTATION_REPORT', 'OTHER')", name="ck_medical_documents_category"),
)

# 18. document_shares
document_shares_table = Table(
    "document_shares",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("document_id", Uuid(as_uuid=False), ForeignKey("medical_documents.id", ondelete="CASCADE"), nullable=False),
    Column("patient_id", Uuid(as_uuid=False), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
    Column("doctor_id", Uuid(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
    Column("appointment_id", Uuid(as_uuid=False), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
    Column("consent_status", String(20), nullable=False, default="GRANTED"),
    Column("granted_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    Column("notes", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_document_shares_doc_doctor", "document_id", "doctor_id"),
    Index("ix_document_shares_doctor_status", "doctor_id", "consent_status"),
    Index("ix_document_shares_patient", "patient_id"),
    Index("uq_document_shares_active", "document_id", "doctor_id", unique=True, postgresql_where=text("consent_status = 'GRANTED'")),
    CheckConstraint("consent_status IN ('GRANTED', 'REVOKED')", name="ck_document_shares_status"),
)

# 19. medical_record_audits
medical_record_audits_table = Table(
    "medical_record_audits",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("actor_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("actor_role", String(50), nullable=False),
    Column("patient_id", Uuid(as_uuid=False), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
    Column("document_id", Uuid(as_uuid=False), ForeignKey("medical_documents.id", ondelete="SET NULL"), nullable=True),
    Column("action", String(50), nullable=False),
    Column("reason", Text, nullable=True),
    Column("metadata", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_medical_audits_patient", "patient_id", "created_at"),
    Index("ix_medical_audits_document", "document_id", "created_at"),
    Index("ix_medical_audits_actor", "actor_id", "created_at"),
    Index("ix_medical_audits_action", "action", "created_at"),
)

# 20. audit_logs
audit_logs_table = Table(
    "audit_logs",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("actor_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("actor_role", String(50), nullable=False),
    Column("action", String(80), nullable=False),
    Column("entity_type", String(80), nullable=False),
    Column("entity_id", String(120), nullable=True),
    Column("hospital_id", Uuid(as_uuid=False), ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True),
    Column("severity", String(20), nullable=False, default="INFO"),
    Column("description", Text, nullable=False),
    Column("metadata", JSON, nullable=False, default=dict),
    Column("ip_address", String(64), nullable=True),
    Column("user_agent", String(500), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_audit_logs_created_at", "created_at"),
    Index("ix_audit_logs_actor", "actor_id", "created_at"),
    Index("ix_audit_logs_role", "actor_role", "created_at"),
    Index("ix_audit_logs_action", "action", "created_at"),
    Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    Index("ix_audit_logs_hospital", "hospital_id", "created_at"),
    Index("ix_audit_logs_severity", "severity", "created_at"),
    CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="ck_audit_logs_severity"),
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
    "notification_preferences": notification_preferences_table,
    "waitlist_entries": waitlist_entries_table,
    "waitlist_offers": waitlist_offers_table,
    "symptom_routing_rules": symptom_routing_rules_table,
    "intake_events": intake_events_table,
    "rescheduling_requests": rescheduling_requests_table,
    "medical_documents": medical_documents_table,
    "document_shares": document_shares_table,
    "medical_record_audits": medical_record_audits_table,
    "audit_logs": audit_logs_table,
}
