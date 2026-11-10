-- ============================================================================
-- NIVARA PHASE 3 DATABASE MIGRATION SCRIPT (FINAL RECONCILED)
-- Intelligent Waitlist Management & Automatic Slot Offers
-- Database: Supabase PostgreSQL (SQLAlchemy 2.0 Async / asyncpg)
-- Instructions: Run this script directly in the Supabase SQL Editor.
-- ============================================================================

-- 1. Create waitlist_offers table if it does not exist
CREATE TABLE IF NOT EXISTS waitlist_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- 2. Schema reconciliations on existing waitlist_offers (from prior iterations)
-- Ensure 'reason' column exists
ALTER TABLE waitlist_offers ADD COLUMN IF NOT EXISTS reason TEXT;

-- Ensure 'created_at' and 'updated_at' exist
ALTER TABLE waitlist_offers ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE waitlist_offers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Ensure 'slot_id' allows NULL
ALTER TABLE waitlist_offers ALTER COLUMN slot_id DROP NOT NULL;

-- Ensure foreign key from waitlist_offers.slot_id has ON DELETE SET NULL
DO $$
DECLARE
    r RECORD;
    valid_fk_found boolean := false;
BEGIN
    FOR r IN (
        SELECT
            tc.constraint_name,
            kcu_ref.table_name AS ref_table,
            kcu_ref.column_name AS ref_col,
            rc.delete_rule AS on_delete_action
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.referential_constraints rc
          ON tc.constraint_name = rc.constraint_name
         AND tc.table_schema = rc.constraint_schema
        JOIN information_schema.key_column_usage kcu_ref
          ON rc.unique_constraint_name = kcu_ref.constraint_name
         AND rc.unique_constraint_schema = kcu_ref.table_schema
        WHERE tc.table_name = 'waitlist_offers'
          AND kcu.column_name = 'slot_id'
          AND tc.constraint_type = 'FOREIGN KEY'
    ) LOOP
        IF r.ref_table = 'appointment_slots'
           AND r.ref_col = 'id'
           AND r.on_delete_action = 'SET NULL'
           AND NOT valid_fk_found THEN
            valid_fk_found := true;
        ELSE
            EXECUTE 'ALTER TABLE waitlist_offers DROP CONSTRAINT ' || quote_ident(r.constraint_name);
        END IF;
    END LOOP;

    IF NOT valid_fk_found THEN
        ALTER TABLE waitlist_offers
            ADD CONSTRAINT fk_waitlist_offers_slot
            FOREIGN KEY (slot_id)
            REFERENCES appointment_slots(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- Fix legacy 'offered_at': copy values into 'created_at' for all rows where offered_at is set,
-- preserving original creation timestamps (without checking created_at IS NULL), then drop column.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'waitlist_offers' AND column_name = 'offered_at'
    ) THEN
        UPDATE waitlist_offers SET created_at = offered_at WHERE offered_at IS NOT NULL;
        ALTER TABLE waitlist_offers DROP COLUMN offered_at;
    END IF;
END $$;

-- Reconcile status CHECK constraint safely without error suppression
DO $$
DECLARE
    r RECORD;
BEGIN
    -- Inspect and remove all existing CHECK constraints on waitlist_offers touching 'status'
    FOR r IN (
        SELECT con.conname
        FROM pg_catalog.pg_constraint con
        JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
        WHERE rel.relname = 'waitlist_offers'
          AND con.contype = 'c'
          AND (con.conname = 'ck_waitlist_offers_status' OR pg_get_constraintdef(con.oid) ILIKE '%status%')
    ) LOOP
        EXECUTE 'ALTER TABLE waitlist_offers DROP CONSTRAINT ' || quote_ident(r.conname);
    END LOOP;

    -- Add canonical status CHECK constraint
    ALTER TABLE waitlist_offers ADD CONSTRAINT ck_waitlist_offers_status
        CHECK (status IN ('PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'CANCELLED'));
END $$;

-- 3. Update appointment_slots with held_until and waitlist_offer_id
ALTER TABLE appointment_slots ADD COLUMN IF NOT EXISTS held_until TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE appointment_slots ADD COLUMN IF NOT EXISTS waitlist_offer_id UUID;

-- Inspect, reconcile, and ensure the foreign key from appointment_slots.waitlist_offer_id
-- to waitlist_offers(id) with ON DELETE SET NULL exists exactly once
DO $$
DECLARE
    r RECORD;
    valid_fk_found boolean := false;
BEGIN
    -- Inspect all existing foreign keys on appointment_slots(waitlist_offer_id)
    FOR r IN (
        SELECT
            tc.constraint_name,
            kcu_ref.table_name AS ref_table,
            kcu_ref.column_name AS ref_col,
            rc.delete_rule AS on_delete_action
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.referential_constraints rc
          ON tc.constraint_name = rc.constraint_name
         AND tc.table_schema = rc.constraint_schema
        JOIN information_schema.key_column_usage kcu_ref
          ON rc.unique_constraint_name = kcu_ref.constraint_name
         AND rc.unique_constraint_schema = kcu_ref.table_schema
        WHERE tc.table_name = 'appointment_slots'
          AND kcu.column_name = 'waitlist_offer_id'
          AND tc.constraint_type = 'FOREIGN KEY'
    ) LOOP
        -- Verify all three: ref_table = waitlist_offers, ref_col = id, on_delete = SET NULL
        IF r.ref_table = 'waitlist_offers'
           AND r.ref_col = 'id'
           AND r.on_delete_action = 'SET NULL'
           AND NOT valid_fk_found THEN
            valid_fk_found := true;
        ELSE
            -- Drop incompatible constraint or redundant duplicate
            EXECUTE 'ALTER TABLE appointment_slots DROP CONSTRAINT ' || quote_ident(r.constraint_name);
        END IF;
    END LOOP;

    -- If no valid FK constraint exists, create it
    IF NOT valid_fk_found THEN
        ALTER TABLE appointment_slots
            ADD CONSTRAINT fk_appointment_slots_waitlist_offer
            FOREIGN KEY (waitlist_offer_id)
            REFERENCES waitlist_offers(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- 4. Partial unique index: A slot can never have more than one active pending offer
CREATE UNIQUE INDEX IF NOT EXISTS uq_waitlist_offers_pending_slot
    ON waitlist_offers (slot_id)
    WHERE status = 'PENDING';

-- 5. Fast lookup indexes for waitlist_offers and appointment_slots
CREATE INDEX IF NOT EXISTS ix_waitlist_offers_patient
    ON waitlist_offers (patient_id, status);

CREATE INDEX IF NOT EXISTS ix_waitlist_offers_entry
    ON waitlist_offers (waitlist_entry_id);

CREATE INDEX IF NOT EXISTS ix_waitlist_offers_doctor
    ON waitlist_offers (doctor_id, status);

CREATE INDEX IF NOT EXISTS ix_waitlist_offers_status_expires
    ON waitlist_offers (status, expires_at);

CREATE INDEX IF NOT EXISTS ix_slots_waitlist_offer
    ON appointment_slots (waitlist_offer_id);

CREATE INDEX IF NOT EXISTS ix_slots_status_held_until
    ON appointment_slots (status, held_until);
