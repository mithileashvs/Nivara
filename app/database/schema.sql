-- =====================================================================
-- Nivara — Intelligent Healthcare Appointment & Management System
-- Supabase PostgreSQL Normalized Database Schema
-- =====================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    role VARCHAR(20) NOT NULL CHECK (role IN ('PATIENT', 'DOCTOR', 'ADMIN')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    managed_hospital_ids JSONB DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_role_active ON users (role, is_active);

-- 2. patients
CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    date_of_birth VARCHAR(10),
    gender VARCHAR(20) NOT NULL DEFAULT 'UNDISCLOSED' CHECK (gender IN ('MALE', 'FEMALE', 'OTHER', 'UNDISCLOSED')),
    basic_information JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_patients_created_at ON patients (created_at);

-- 3. hospitals
CREATE TABLE IF NOT EXISTS hospitals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    name_normalized VARCHAR(255) NOT NULL,
    address TEXT NOT NULL,
    location JSONB NOT NULL DEFAULT '{}'::jsonb,
    contact JSONB NOT NULL DEFAULT '{}'::jsonb,
    appointment_intake_status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (appointment_intake_status IN ('OPEN', 'CLOSED')),
    department_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_hospitals_name ON hospitals (name_normalized);
CREATE INDEX IF NOT EXISTS ix_hospitals_intake ON hospitals (appointment_intake_status);

-- 4. departments
CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id UUID NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    name_normalized VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    appointment_intake_status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (appointment_intake_status IN ('OPEN', 'CLOSED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_departments_hospital_name UNIQUE (hospital_id, name_normalized)
);
CREATE INDEX IF NOT EXISTS ix_departments_name ON departments (name_normalized);

-- 5. doctors
CREATE TABLE IF NOT EXISTS doctors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    specialty VARCHAR(255) NOT NULL,
    specialty_normalized VARCHAR(255) NOT NULL,
    department_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    hospital_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    experience INTEGER NOT NULL DEFAULT 0,
    consultation_fee DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    consultation_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    availability_status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (availability_status IN ('OPEN', 'CLOSED')),
    profile_status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (profile_status IN ('PENDING', 'ACTIVE', 'SUSPENDED')),
    rating_sum INTEGER NOT NULL DEFAULT 0,
    rating_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_doctors_specialty ON doctors (specialty_normalized);
CREATE INDEX IF NOT EXISTS ix_doctors_status ON doctors (profile_status, availability_status);

-- 6. doctor_availability
CREATE TABLE IF NOT EXISTS doctor_availability (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    hospital_id UUID NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    date VARCHAR(10) NOT NULL,
    start_time VARCHAR(5) NOT NULL,
    end_time VARCHAR(5) NOT NULL,
    slot_duration INTEGER NOT NULL DEFAULT 30,
    status VARCHAR(20) NOT NULL DEFAULT 'WORKING' CHECK (status IN ('WORKING', 'BLOCKED')),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_availability_doctor_date ON doctor_availability (doctor_id, date);

-- 7. appointment_slots
CREATE TABLE IF NOT EXISTS appointment_slots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    hospital_id UUID NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    date VARCHAR(10) NOT NULL,
    start_time VARCHAR(5) NOT NULL,
    end_time VARCHAR(5) NOT NULL,
    start_at TIMESTAMP NOT NULL,
    end_at TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE', 'HELD', 'BOOKED', 'BLOCKED')),
    appointment_id UUID,
    held_until TIMESTAMP,
    waitlist_offer_id UUID,
    availability_id UUID REFERENCES doctor_availability(id) ON DELETE CASCADE,
    block_source VARCHAR(50),
    blocked_by_availability_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_slots_doctor_date_start UNIQUE (doctor_id, date, start_time)
);
CREATE INDEX IF NOT EXISTS ix_slots_doctor_date_status ON appointment_slots (doctor_id, date, status);
CREATE INDEX IF NOT EXISTS ix_slots_status_held_until ON appointment_slots (status, held_until);
CREATE INDEX IF NOT EXISTS ix_slots_facility_status_start ON appointment_slots (hospital_id, department_id, status, start_at);
CREATE INDEX IF NOT EXISTS ix_slots_availability ON appointment_slots (availability_id);
CREATE INDEX IF NOT EXISTS ix_slots_appointment ON appointment_slots (appointment_id);
CREATE INDEX IF NOT EXISTS ix_slots_waitlist_offer ON appointment_slots (waitlist_offer_id);
CREATE INDEX IF NOT EXISTS ix_slots_hospital_date_status ON appointment_slots (hospital_id, date, status);

-- 8. appointments
CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    patient_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    patient_name VARCHAR(255) NOT NULL,
    doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    doctor_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doctor_name VARCHAR(255) NOT NULL,
    hospital_id UUID NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    slot_id UUID NOT NULL REFERENCES appointment_slots(id) ON DELETE CASCADE,
    appointment_date VARCHAR(10) NOT NULL,
    start_time VARCHAR(5) NOT NULL,
    end_time VARCHAR(5) NOT NULL,
    start_at TIMESTAMP NOT NULL,
    end_at TIMESTAMP NOT NULL,
    consultation_type VARCHAR(50) NOT NULL,
    reason TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'REQUESTED' CHECK (status IN ('REQUESTED', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', 'RESCHEDULE_REQUESTED')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    status_reason TEXT,
    reminder_sent BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_appointments_active_slot ON appointments (slot_id) WHERE is_active = TRUE;
CREATE UNIQUE INDEX IF NOT EXISTS uq_appointments_active_patient_start ON appointments (patient_id, start_at) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS ix_appointments_slot ON appointments (slot_id);
CREATE INDEX IF NOT EXISTS ix_appointments_doctor_status ON appointments (doctor_id, status, start_at);
CREATE INDEX IF NOT EXISTS ix_appointments_patient_status ON appointments (patient_id, status, start_at);
CREATE INDEX IF NOT EXISTS ix_appointments_date ON appointments (appointment_date);
CREATE INDEX IF NOT EXISTS ix_appointments_status_start ON appointments (status, start_at);
CREATE INDEX IF NOT EXISTS ix_appointments_hospital_date_status ON appointments (hospital_id, appointment_date, status);
CREATE INDEX IF NOT EXISTS ix_appointments_department_date_status ON appointments (department_id, appointment_date, status);

-- 9. appointment_history
CREATE TABLE IF NOT EXISTS appointment_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    previous_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    changed_by_role VARCHAR(50) NOT NULL,
    reason TEXT,
    previous_date VARCHAR(10),
    previous_time VARCHAR(5),
    new_date VARCHAR(10),
    new_time VARCHAR(5),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_history_appointment ON appointment_history (appointment_id, created_at);

-- 10. medical_records
CREATE TABLE IF NOT EXISTS medical_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    appointment_id UUID NOT NULL UNIQUE REFERENCES appointments(id) ON DELETE CASCADE,
    notes TEXT NOT NULL,
    documents JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_records_patient ON medical_records (patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_records_doctor ON medical_records (doctor_id, created_at DESC);

-- 11. reviews
CREATE TABLE IF NOT EXISTS reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    appointment_id UUID NOT NULL UNIQUE REFERENCES appointments(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_reviews_doctor ON reviews (doctor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_reviews_patient ON reviews (patient_id);

-- 12. notifications
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'APPOINTMENT',
    action_url VARCHAR(500),
    related_appointment_id UUID,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_notifications_user ON notifications (user_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_notifications_user_category ON notifications (user_id, category, created_at DESC);

-- 12b. notification_preferences
CREATE TABLE IF NOT EXISTS notification_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_notification_preferences_user_category UNIQUE (user_id, category)
);
CREATE INDEX IF NOT EXISTS ix_notification_preferences_user ON notification_preferences (user_id);

-- 13. waitlist_entries
CREATE TABLE IF NOT EXISTS waitlist_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    patient_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doctor_id UUID REFERENCES doctors(id) ON DELETE CASCADE,
    department_id UUID REFERENCES departments(id) ON DELETE CASCADE,
    hospital_id UUID REFERENCES hospitals(id) ON DELETE CASCADE,
    specialty VARCHAR(255),
    specialty_normalized VARCHAR(255),
    date_from VARCHAR(10) NOT NULL,
    date_to VARCHAR(10) NOT NULL,
    time_from VARCHAR(5),
    time_to VARCHAR(5),
    consultation_type VARCHAR(50),
    existing_appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'FULFILLED', 'CANCELLED', 'EXPIRED')),
    notified_slot_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    fulfilled_appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_waitlist_doctor ON waitlist_entries (doctor_id);
CREATE INDEX IF NOT EXISTS ix_waitlist_department ON waitlist_entries (department_id);
CREATE INDEX IF NOT EXISTS ix_waitlist_hospital ON waitlist_entries (hospital_id);
CREATE INDEX IF NOT EXISTS ix_waitlist_status_dates ON waitlist_entries (status, date_from, date_to);
CREATE INDEX IF NOT EXISTS ix_waitlist_patient ON waitlist_entries (patient_id, status);

-- 13b. waitlist_offers
CREATE TABLE IF NOT EXISTS waitlist_offers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    waitlist_entry_id UUID NOT NULL REFERENCES waitlist_entries(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    slot_id UUID REFERENCES appointment_slots(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'CANCELLED')),
    expires_at TIMESTAMPTZ NOT NULL,
    responded_at TIMESTAMPTZ,
    reason TEXT,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_waitlist_offers_pending_slot ON waitlist_offers (slot_id) WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS ix_waitlist_offers_patient ON waitlist_offers (patient_id, status);
CREATE INDEX IF NOT EXISTS ix_waitlist_offers_entry ON waitlist_offers (waitlist_entry_id);
CREATE INDEX IF NOT EXISTS ix_waitlist_offers_doctor ON waitlist_offers (doctor_id, status);
CREATE INDEX IF NOT EXISTS ix_waitlist_offers_status_expires ON waitlist_offers (status, expires_at);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_constraint con
        JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
        WHERE rel.relname = 'appointment_slots'
          AND con.conname = 'fk_appointment_slots_waitlist_offer'
    ) THEN
        ALTER TABLE appointment_slots
            ADD CONSTRAINT fk_appointment_slots_waitlist_offer
            FOREIGN KEY (waitlist_offer_id)
            REFERENCES waitlist_offers(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- 14. symptom_routing_rules
CREATE TABLE IF NOT EXISTS symptom_routing_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    department_name VARCHAR(255) NOT NULL,
    department_name_normalized VARCHAR(255) NOT NULL,
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    is_emergency BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_rules_department ON symptom_routing_rules (department_name_normalized);

-- 15. intake_events
CREATE TABLE IF NOT EXISTS intake_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_type VARCHAR(50) NOT NULL,
    target_id UUID NOT NULL,
    hospital_id UUID NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    previous_status VARCHAR(20) NOT NULL,
    new_status VARCHAR(20) NOT NULL,
    changed_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_intake_events_target ON intake_events (target_type, target_id, created_at DESC);

-- 16. rescheduling_requests
CREATE TABLE IF NOT EXISTS rescheduling_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    patient_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    patient_name VARCHAR(255),
    doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    doctor_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doctor_name VARCHAR(255),
    hospital_id UUID NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    old_slot_id UUID NOT NULL REFERENCES appointment_slots(id) ON DELETE CASCADE,
    requested_slot_id UUID NOT NULL REFERENCES appointment_slots(id) ON DELETE CASCADE,
    old_appointment_date VARCHAR(10),
    old_start_time VARCHAR(5),
    old_end_time VARCHAR(5),
    requested_appointment_date VARCHAR(10),
    requested_start_time VARCHAR(5),
    requested_end_time VARCHAR(5),
    reason TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'REQUESTED' CHECK (status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'CANCELLED')),
    doctor_response TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_reschedule_appointment ON rescheduling_requests (appointment_id);
CREATE INDEX IF NOT EXISTS ix_reschedule_patient_status ON rescheduling_requests (patient_id, status);
CREATE INDEX IF NOT EXISTS ix_reschedule_doctor_status ON rescheduling_requests (doctor_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_reschedule_active_appointment ON rescheduling_requests (appointment_id) WHERE status = 'REQUESTED';

-- 17. medical_documents
CREATE TABLE IF NOT EXISTS medical_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    patient_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('LAB_REPORT', 'PRESCRIPTION', 'IMAGING', 'DISCHARGE_SUMMARY', 'CONSULTATION_REPORT', 'OTHER')),
    description TEXT,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    storage_provider VARCHAR(50) NOT NULL DEFAULT 'LOCAL',
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_medical_documents_patient ON medical_documents (patient_id, is_deleted, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_medical_documents_category ON medical_documents (category);
CREATE INDEX IF NOT EXISTS ix_medical_documents_appointment ON medical_documents (appointment_id);

-- 18. document_shares
CREATE TABLE IF NOT EXISTS document_shares (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES medical_documents(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    consent_status VARCHAR(20) NOT NULL DEFAULT 'GRANTED' CHECK (consent_status IN ('GRANTED', 'REVOKED')),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_document_shares_doc_doctor ON document_shares (document_id, doctor_id);
CREATE INDEX IF NOT EXISTS ix_document_shares_doctor_status ON document_shares (doctor_id, consent_status);
CREATE INDEX IF NOT EXISTS ix_document_shares_patient ON document_shares (patient_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_document_shares_active ON document_shares (document_id, doctor_id) WHERE consent_status = 'GRANTED';

-- 19. medical_record_audits
CREATE TABLE IF NOT EXISTS medical_record_audits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_role VARCHAR(50) NOT NULL,
    patient_id UUID REFERENCES patients(id) ON DELETE SET NULL,
    document_id UUID REFERENCES medical_documents(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_medical_audits_patient ON medical_record_audits (patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_medical_audits_document ON medical_record_audits (document_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_medical_audits_actor ON medical_record_audits (actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_medical_audits_action ON medical_record_audits (action, created_at DESC);

-- 20. audit_logs (Phase 6 centralized append-only audit & security log)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_role VARCHAR(50) NOT NULL,
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(80) NOT NULL,
    entity_id VARCHAR(120),
    hospital_id UUID REFERENCES hospitals(id) ON DELETE SET NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    description TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address VARCHAR(64),
    user_agent VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_logs_actor ON audit_logs (actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_logs_role ON audit_logs (actor_role, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_hospital ON audit_logs (hospital_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_logs_severity ON audit_logs (severity, created_at DESC);
