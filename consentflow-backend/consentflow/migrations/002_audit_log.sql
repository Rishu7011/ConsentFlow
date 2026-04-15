-- ============================================================
-- ConsentFlow — Migration 002: Audit log table (Step 7)
-- ============================================================

-- ── audit_log ───────────────────────────────────────────────────────────────────
-- Persistent, queryable record of every consent enforcement action taken by
-- the four pipeline gates.  Inserted by the OTel gate wrappers at call time.
--
-- Columns
-- -------
-- user_id        TEXT (not UUID) — training/monitoring gates may emit "UNKNOWN"
--                for aggregate alerts where a specific user cannot be resolved.
-- gate_name      Which gate produced this record:
--                  'dataset_gate' | 'inference_gate' | 'training_gate' | 'monitoring_gate'
-- action_taken   What the gate did:
--                  'passed' | 'blocked' | 'quarantined' | 'alerted' | 'anonymized'
-- consent_status Effective status at decision time: 'granted' | 'revoked'
-- purpose        Consent purpose string (nullable — not all gates supply it)
-- metadata       JSONB bag for gate-specific extras (run_id, alert severity, …)
-- trace_id       OTel W3C trace-id so Grafana Explore can link log → trace
CREATE TABLE IF NOT EXISTS audit_log (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    event_time     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    user_id        TEXT         NOT NULL,
    gate_name      TEXT         NOT NULL,
    action_taken   TEXT         NOT NULL,
    consent_status TEXT         NOT NULL,
    purpose        TEXT,
    metadata       JSONB,
    trace_id       TEXT
);

-- Fast lookups by user (audit trail per user)
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id
    ON audit_log (user_id);

-- Time-ordered query support (default sort for /audit/trail)
CREATE INDEX IF NOT EXISTS idx_audit_log_event_time
    ON audit_log (event_time DESC);

-- Filter by gate name (dashboard gate-level block counts)
CREATE INDEX IF NOT EXISTS idx_audit_log_gate_name
    ON audit_log (gate_name);
