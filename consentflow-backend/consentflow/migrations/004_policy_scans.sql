-- ============================================================
-- ConsentFlow — Migration 004: Policy Auditor table (Gate 05)
-- ============================================================

-- ── policy_scans ─────────────────────────────────────────────────────────────
-- Records every privacy-policy / Terms-of-Service scan performed by Gate 05.
-- Each row captures the full set of red-flag findings the LLM analyser found,
-- the computed overall risk level, and a back-reference to the audit_log row
-- written at scan time.
--
-- Columns
-- -------
-- integration_name   Human-readable name of the plugin / integration scanned
--                    (e.g. "Claude Plugin", "OpenAI Codex").
-- policy_url         Source URL the scanner fetched, if any.
-- policy_text_hash   SHA-256 hex-digest of the raw policy text; allows the
--                    service to skip re-scanning identical documents.
-- overall_risk_level Aggregate risk verdict: 'low' | 'medium' | 'high' | 'critical'.
-- findings_count     Denormalised count of items in the findings array —
--                    lets the list endpoint avoid deserialising JSONB.
-- findings           JSONB array of finding objects.  Each element shape:
--                      {
--                        "id":                "<string>",
--                        "severity":          "low|medium|high|critical",
--                        "category":          "<string>",
--                        "clause_excerpt":    "<string>",
--                        "explanation":       "<string>",
--                        "article_reference": "<string>"
--                      }
-- raw_summary        LLM-generated plain-English summary of the scan.
-- audit_log_id       Optional FK to audit_log(id) — links this scan result to
--                    the enforcement event that triggered it.

CREATE TABLE IF NOT EXISTS policy_scans (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    scanned_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    integration_name  TEXT         NOT NULL,
    policy_url        TEXT,
    policy_text_hash  TEXT,
    overall_risk_level TEXT        NOT NULL
                                   CHECK (overall_risk_level IN ('low', 'medium', 'high', 'critical')),
    findings_count    INTEGER      NOT NULL DEFAULT 0,
    findings          JSONB        NOT NULL DEFAULT '[]'::jsonb,
    raw_summary       TEXT,
    audit_log_id      UUID         REFERENCES audit_log (id) ON DELETE SET NULL
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- Default chronological ordering for list / dashboard queries.
CREATE INDEX IF NOT EXISTS idx_policy_scans_scanned_at
    ON policy_scans (scanned_at DESC);

-- Filter / group-by risk level (dashboard risk breakdown).
CREATE INDEX IF NOT EXISTS idx_policy_scans_risk_level
    ON policy_scans (overall_risk_level);

-- Lookup all scans for a specific integration (history view).
CREATE INDEX IF NOT EXISTS idx_policy_scans_integration_name
    ON policy_scans (integration_name);
