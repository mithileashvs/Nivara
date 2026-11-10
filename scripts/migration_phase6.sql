-- ============================================================================
-- NIVARA PHASE 6 DATABASE MIGRATION SCRIPT
-- Centralized Audit Logs & Advanced Administration
-- Database: Supabase PostgreSQL (SQLAlchemy 2.0 Async / asyncpg)
-- Instructions: Run this script directly in the Supabase SQL Editor or via
--               `python scripts/migration_phase6.py`.
-- Note: Safe and idempotent. Does not alter or remove existing Phase 1-5 data.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Centralized append-only audit_logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_role VARCHAR(50) NOT NULL,
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(80) NOT NULL,
    entity_id VARCHAR(120),
    hospital_id UUID REFERENCES hospitals(id) ON DELETE SET NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'INFO',
    description TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address VARCHAR(64),
    user_agent VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Reconcile severity CHECK constraint safely and idempotently
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = current_schema()
          AND rel.relname = 'audit_logs'
          AND con.conname = 'ck_audit_logs_severity'
          AND con.contype = 'c'
    ) THEN
        ALTER TABLE audit_logs
            ADD CONSTRAINT ck_audit_logs_severity
            CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL'));
    END IF;
END $$;

-- 3. Performance indexes for Audit Explorer, Hospital Scoping & Security Monitoring
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at
    ON audit_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_logs_actor
    ON audit_logs (actor_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_logs_role
    ON audit_logs (actor_role, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_logs_action
    ON audit_logs (action, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_logs_entity
    ON audit_logs (entity_type, entity_id);

CREATE INDEX IF NOT EXISTS ix_audit_logs_hospital
    ON audit_logs (hospital_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_logs_severity
    ON audit_logs (severity, created_at DESC);
