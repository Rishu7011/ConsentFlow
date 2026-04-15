export const DEMO_UUID = "550e8400-e29b-41d4-a716-446655440000";
// Use NEXT_PUBLIC_BACKEND_URL env var in Docker / staging / production.
// Falls back to localhost:8000 for local development.
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
