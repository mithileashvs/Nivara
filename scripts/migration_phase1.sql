-- =====================================================================
-- Nivara Phase 1 Migration: Advanced Appointment Management
-- Target: Supabase PostgreSQL
-- =====================================================================

-- 1. Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Reconcile status CHECK constraint on appointments table to allow RESCHEDULE_REQUESTED
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT con.conname
        FROM pg_catalog.pg_constraint con
        JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
        JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = current_schema()
          AND rel.relname = 'appointments'
          AND con.contype = 'c'
          AND (con.conname = 'ck_appointments_status' OR pg_get_constraintdef(con.oid) ILIKE '%status%')
    ) LOOP
        EXECUTE 'ALTER TABLE appointments DROP CONSTRAINT ' || quote_ident(r.conname);
    END LOOP;

    ALTER TABLE appointments ADD CONSTRAINT ck_appointments_status
        CHECK (status IN ('REQUESTED', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', 'RESCHEDULE_REQUESTED'));
END $$;

-- 3. Extend appointment_history table with date/time and metadata columns
ALTER TABLE appointment_history ADD COLUMN IF NOT EXISTS previous_date VARCHAR(10);
ALTER TABLE appointment_history ADD COLUMN IF NOT EXISTS previous_time VARCHAR(5);
ALTER TABLE appointment_history ADD COLUMN IF NOT EXISTS new_date VARCHAR(10);
ALTER TABLE appointment_history ADD COLUMN IF NOT EXISTS new_time VARCHAR(5);
ALTER TABLE appointment_history ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- 4. Create rescheduling_requests table
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

-- 5. Create indexes on rescheduling_requests
CREATE INDEX IF NOT EXISTS ix_reschedule_appointment ON rescheduling_requests (appointment_id);
CREATE INDEX IF NOT EXISTS ix_reschedule_patient_status ON rescheduling_requests (patient_id, status);
CREATE INDEX IF NOT EXISTS ix_reschedule_doctor_status ON rescheduling_requests (doctor_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_reschedule_active_appointment ON rescheduling_requests (appointment_id) WHERE status = 'REQUESTED';
