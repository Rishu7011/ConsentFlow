-- ============================================================
-- ConsentFlow — Migration 006: Consent Freeze Log
-- ============================================================
-- Plan 1.2 — Records the moment consent was revoked and how many
-- memories were in the RAG store at that instant.
-- Used by the frontend to display "2 facts (frozen forever)".

CREATE TABLE IF NOT EXISTS consent_freeze_log (
    user_id         TEXT        PRIMARY KEY,
    frozen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    frozen_at_count INTEGER     NOT NULL  -- memory count at freeze time
);
