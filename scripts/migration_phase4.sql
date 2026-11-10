-- ============================================================================
-- NIVARA PHASE 4 DATABASE MIGRATION SCRIPT
-- Medical Records Enhancement: Documents, Patient-Controlled Consent & Audits
-- Database: Supabase PostgreSQL (SQLAlchemy 2.0 Async / asyncpg)
-- Instructions: Run this script directly in the Supabase SQL Editor or via
--               `python scripts/migration_phase4.py`.
-- ============================================================================

-- 1. Create medical_documents table
CREATE TABLE IF NOT EXISTS medical_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- Indexes for medical_documents
CREATE INDEX IF NOT EXISTS ix_medical_documents_patient
    ON medical_documents (patient_id, is_deleted, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_medical_documents_category
    ON medical_documents (category);

CREATE INDEX IF NOT EXISTS ix_medical_documents_appointment
    ON medical_documents (appointment_id);


-- 2. Create document_shares table (Patient-Controlled Consent)
CREATE TABLE IF NOT EXISTS document_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- Standard indexes for document_shares
CREATE INDEX IF NOT EXISTS ix_document_shares_doc_doctor
    ON document_shares (document_id, doctor_id);

CREATE INDEX IF NOT EXISTS ix_document_shares_doctor_status
    ON document_shares (doctor_id, consent_status);

CREATE INDEX IF NOT EXISTS ix_document_shares_patient
    ON document_shares (patient_id);

-- Reconcile any legacy duplicate GRANTED shares before enforcing partial unique index
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY document_id, doctor_id ORDER BY granted_at DESC, created_at DESC) AS rn
    FROM document_shares
    WHERE consent_status = 'GRANTED'
)
UPDATE document_shares
SET consent_status = 'REVOKED',
    revoked_at = COALESCE(revoked_at, NOW()),
    updated_at = NOW()
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- Partial unique index: at most ONE active GRANTED consent per (document_id, doctor_id),
-- while preserving all historical REVOKED rows.
CREATE UNIQUE INDEX IF NOT EXISTS uq_document_shares_active
    ON document_shares (document_id, doctor_id)
    WHERE consent_status = 'GRANTED';


-- 3. Create medical_record_audits table (Access & Modification Auditing)
-- Foreign keys use ON DELETE SET NULL so legal audit trails are never purged when users/patients/docs are deleted.
CREATE TABLE IF NOT EXISTS medical_record_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_role VARCHAR(50) NOT NULL,
    patient_id UUID REFERENCES patients(id) ON DELETE SET NULL,
    document_id UUID REFERENCES medical_documents(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Reconcile nullable audit columns & foreign keys if table existed from earlier Phase 4 iteration
DO $$
DECLARE
    r RECORD;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'medical_record_audits' AND column_name = 'actor_id' AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE medical_record_audits ALTER COLUMN actor_id DROP NOT NULL;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'medical_record_audits' AND column_name = 'patient_id' AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE medical_record_audits ALTER COLUMN patient_id DROP NOT NULL;
    END IF;

    -- Drop any FK on actor_id, patient_id, or document_id whose delete_rule is not SET NULL
    FOR r IN (
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.referential_constraints rc
          ON tc.constraint_name = rc.constraint_name AND tc.table_schema = rc.constraint_schema
        WHERE tc.table_schema = current_schema()
          AND tc.table_name = 'medical_record_audits'
          AND tc.constraint_type = 'FOREIGN KEY'
          AND kcu.column_name IN ('actor_id', 'patient_id', 'document_id')
          AND rc.delete_rule <> 'SET NULL'
    ) LOOP
        EXECUTE 'ALTER TABLE medical_record_audits DROP CONSTRAINT IF EXISTS ' || quote_ident(r.constraint_name);
    END LOOP;

    -- Ensure FKs exist with ON DELETE SET NULL
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = current_schema()
          AND tc.table_name = 'medical_record_audits'
          AND tc.constraint_type = 'FOREIGN KEY'
          AND kcu.column_name = 'actor_id'
    ) THEN
        ALTER TABLE medical_record_audits
            ADD CONSTRAINT fk_medical_record_audits_actor
            FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = current_schema()
          AND tc.table_name = 'medical_record_audits'
          AND tc.constraint_type = 'FOREIGN KEY'
          AND kcu.column_name = 'patient_id'
    ) THEN
        ALTER TABLE medical_record_audits
            ADD CONSTRAINT fk_medical_record_audits_patient
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = current_schema()
          AND tc.table_name = 'medical_record_audits'
          AND tc.constraint_type = 'FOREIGN KEY'
          AND kcu.column_name = 'document_id'
    ) THEN
        ALTER TABLE medical_record_audits
            ADD CONSTRAINT fk_medical_record_audits_document
            FOREIGN KEY (document_id) REFERENCES medical_documents(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Indexes for medical_record_audits
CREATE INDEX IF NOT EXISTS ix_medical_audits_patient
    ON medical_record_audits (patient_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_medical_audits_document
    ON medical_record_audits (document_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_medical_audits_actor
    ON medical_record_audits (actor_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_medical_audits_action
    ON medical_record_audits (action, created_at DESC);
