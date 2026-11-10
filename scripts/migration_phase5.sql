-- ============================================================================
-- NIVARA PHASE 5 DATABASE MIGRATION SCRIPT
-- Advanced Operational Analytics: Composite Read-Query Indexes
-- Database: Supabase PostgreSQL (SQLAlchemy 2.0 Async / asyncpg)
-- Instructions: Run this script directly in the Supabase SQL Editor or via
--               `python scripts/migration_phase5.py`.
-- Note: Zero table alterations or data mutations. Safe and idempotent.
-- ============================================================================

-- 1. Hospital-scoped & date-range appointment aggregations
CREATE INDEX IF NOT EXISTS ix_appointments_hospital_date_status
    ON appointments (hospital_id, appointment_date, status);

-- 2. Department-scoped & date-range appointment aggregations
CREATE INDEX IF NOT EXISTS ix_appointments_department_date_status
    ON appointments (department_id, appointment_date, status);

-- 3. Timezone-aware patient registration trend aggregations
CREATE INDEX IF NOT EXISTS ix_patients_created_at
    ON patients (created_at);

-- 4. Hospital-scoped slot availability & utilization aggregations
CREATE INDEX IF NOT EXISTS ix_slots_hospital_date_status
    ON appointment_slots (hospital_id, date, status);
