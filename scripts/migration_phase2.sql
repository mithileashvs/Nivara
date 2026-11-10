-- ============================================================================
-- NIVARA PHASE 2 DATABASE MIGRATION SCRIPT
-- Advanced Notification Management System & Preferences
-- Run this script in the Supabase SQL Editor or via `python scripts/migration_phase2.py`.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Extend notifications table with category, action_url, read_at
ALTER TABLE notifications
    ADD COLUMN IF NOT EXISTS category VARCHAR(50) NOT NULL DEFAULT 'APPOINTMENT',
    ADD COLUMN IF NOT EXISTS action_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ;

-- Backfill categories for existing notifications based on type
UPDATE notifications
SET category = CASE
    WHEN type IN ('APPOINTMENT_REQUESTED', 'APPOINTMENT_ACCEPTED', 'APPOINTMENT_REJECTED', 'APPOINTMENT_REMINDER') THEN 'APPOINTMENT'
    WHEN type IN ('APPOINTMENT_RESCHEDULED', 'RESCHEDULE_REQUESTED', 'RESCHEDULE_APPROVED', 'RESCHEDULE_REJECTED') THEN 'RESCHEDULING'
    WHEN type IN ('APPOINTMENT_CANCELLED') THEN 'CANCELLATION'
    WHEN type IN (
        'WAITLIST_SLOT_AVAILABLE',
        'WAITLIST_ELIGIBLE',
        'WAITLIST_EXPIRED',
        'WAITLIST_OFFER_AVAILABLE',
        'WAITLIST_OFFER_ACCEPTED',
        'WAITLIST_OFFER_DECLINED'
    ) THEN 'WAITLIST'
    ELSE 'SYSTEM'
END
WHERE category = 'APPOINTMENT'
  AND type NOT IN ('APPOINTMENT_REQUESTED', 'APPOINTMENT_ACCEPTED', 'APPOINTMENT_REJECTED', 'APPOINTMENT_REMINDER');

-- Backfill read_at for existing read notifications
UPDATE notifications
SET read_at = updated_at
WHERE is_read = TRUE AND read_at IS NULL;

-- 2. Create index for fast user + category queries
CREATE INDEX IF NOT EXISTS ix_notifications_user_category
    ON notifications (user_id, category, created_at DESC);

-- 3. Create notification_preferences table
CREATE TABLE IF NOT EXISTS notification_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_notification_preferences_user_category UNIQUE (user_id, category)
);

CREATE INDEX IF NOT EXISTS ix_notification_preferences_user
    ON notification_preferences (user_id);
