-- migrations/004_consent_freeze_log_add_purpose.sql

-- Step 1: Add purpose column (nullable first, so existing rows don't break)
ALTER TABLE consent_freeze_log
    ADD COLUMN purpose TEXT;

-- Step 2: Backfill existing rows.
-- These pre-migration rows have unknown purpose, so treat them as frozen
-- for all known purposes to stay conservative (opt-out safe).
INSERT INTO consent_freeze_log (user_id, purpose, frozen_at)
SELECT DISTINCT user_id, p.purpose, NOW()
FROM consent_freeze_log
CROSS JOIN (VALUES ('model_training'), ('analytics')) AS p(purpose)
WHERE purpose IS NULL
ON CONFLICT (user_id, purpose) DO NOTHING;

-- Step 3: Remove the ambiguous old rows (purpose IS NULL)
DELETE FROM consent_freeze_log WHERE purpose IS NULL;

-- Step 4: Make purpose NOT NULL and add the composite unique constraint
ALTER TABLE consent_freeze_log
    ALTER COLUMN purpose SET NOT NULL;

ALTER TABLE consent_freeze_log
    DROP CONSTRAINT IF EXISTS consent_freeze_log_pkey;

ALTER TABLE consent_freeze_log
    ADD CONSTRAINT consent_freeze_log_pkey PRIMARY KEY (user_id, purpose);
