-- ============================================================
-- ConsentFlow — Migration 001: Initial schema
-- ============================================================

-- Enable pgcrypto for gen_random_uuid() on older Postgres versions.
-- On Postgres 13+ gen_random_uuid() is built-in; this is a safe no-op.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── users ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email      TEXT        NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── consent_records ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS consent_records (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    data_type  TEXT        NOT NULL,
    purpose    TEXT        NOT NULL,
    status     TEXT        NOT NULL CHECK (status IN ('granted', 'revoked')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique constraint: one record per (user, purpose, data_type) triple
-- Allows upsert via ON CONFLICT DO UPDATE
CREATE UNIQUE INDEX IF NOT EXISTS idx_consent_user_purpose_datatype
    ON consent_records (user_id, purpose, data_type);

-- Fast lookup index: (user_id, purpose, status) — covers the most common query pattern
CREATE INDEX IF NOT EXISTS idx_consent_user_purpose_status
    ON consent_records (user_id, purpose, status);
