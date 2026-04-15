-- ============================================================
-- ConsentFlow — Migration 003: Seed demo user
-- ============================================================
-- Inserts the canonical demo user so that the well-known test UUID
-- (550e8400-e29b-41d4-a716-446655440000) is always present in the
-- users table.  This prevents FK violations when running manual
-- tests or hitting the API docs (/docs) straight after startup.
--
-- ON CONFLICT DO NOTHING makes this idempotent — safe to re-apply.
-- Clean up any existing row that has the demo email but a random ID
DELETE FROM users 
WHERE email = 'demo@consentflow.dev' 
  AND id != '550e8400-e29b-41d4-a716-446655440000';

-- Insert with the canonical UUID
INSERT INTO users (id, email)
VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    'demo@consentflow.dev'
)
ON CONFLICT (email) DO NOTHING;
