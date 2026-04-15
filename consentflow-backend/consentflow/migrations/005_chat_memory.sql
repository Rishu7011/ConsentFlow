-- ============================================================
-- ConsentFlow — Migration 005: Chat Memory (RAG)
-- ============================================================
-- Plan 1.2 — RAG knowledge base + full chat log for the demo.

-- ── user_memory ────────────────────────────────────────────────────────────────
-- Personal RAG knowledge base per user.
-- Facts are extracted from incoming messages by memory_store.extract_and_store()
-- after Presidio PII scanning. New rows are ONLY written while consent is granted.
-- After revocation the table is frozen — reads still work, writes are blocked.

CREATE TABLE IF NOT EXISTS user_memory (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id      TEXT        NOT NULL,
    memory_text  TEXT        NOT NULL,    -- e.g. "User's name is Rishabh"
    source_msg   TEXT        NOT NULL,    -- original message that generated this fact
    pii_detected TEXT[]      DEFAULT '{}' -- PII entity types found: ["PERSON", "LOCATION"]
);

CREATE INDEX IF NOT EXISTS idx_user_memory_user_id ON user_memory (user_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_created  ON user_memory (created_at DESC);

-- ── chat_log ───────────────────────────────────────────────────────────────────
-- Full chat history for display in the demo UI.
-- Stores both the original message and the Presidio-redacted version so the
-- frontend can highlight <REDACTED> tags after consent is revoked.

CREATE TABLE IF NOT EXISTS chat_log (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_time       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id          TEXT        NOT NULL,
    message          TEXT        NOT NULL,    -- original message (as typed)
    message_redacted TEXT        NOT NULL,    -- Presidio-redacted version
    reply            TEXT        NOT NULL,    -- Gemini response
    trained          BOOLEAN     NOT NULL DEFAULT false, -- was memory stored?
    memory_used      TEXT[]      DEFAULT '{}', -- memory chunks passed to Gemini
    pii_detected     TEXT[]      DEFAULT '{}', -- entity types found by Presidio
    consent_status   TEXT        NOT NULL      -- "granted" | "revoked" at message time
);

CREATE INDEX IF NOT EXISTS idx_chat_log_user_id    ON chat_log (user_id);
CREATE INDEX IF NOT EXISTS idx_chat_log_event_time ON chat_log (event_time DESC);
