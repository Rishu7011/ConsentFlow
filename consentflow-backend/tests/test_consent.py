"""
tests/test_consent.py — Unit tests for /consent endpoints.

Uses in-memory fakes injected via conftest — no real services required.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

USER_ID = "550e8400-e29b-41d4-a716-446655440000"
PURPOSE = "analytics"

FAKE_ROW = {
    "id": uuid4(),
    "user_id": UUID(USER_ID),
    "data_type": "pii",
    "purpose": PURPOSE,
    "status": "granted",
    "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
}


# ── POST /consent ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_consent(client: AsyncClient):
    client.fake_pool.rows = [FAKE_ROW]  # type: ignore[attr-defined]

    response = await client.post(
        "/consent",
        json={
            "user_id": USER_ID,
            "data_type": "pii",
            "purpose": PURPOSE,
            "status": "granted",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "granted"
    assert body["purpose"] == PURPOSE


# ── GET /consent/{user_id}/{purpose} — cache miss ─────────────────────────────

@pytest.mark.asyncio
async def test_get_consent_cache_miss(client: AsyncClient):
    client.fake_pool.rows = [FAKE_ROW]  # type: ignore[attr-defined]

    response = await client.get(f"/consent/{USER_ID}/{PURPOSE}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "granted"
    assert body["cached"] is False


# ── GET /consent/{user_id}/{purpose} — cache hit ──────────────────────────────

@pytest.mark.asyncio
async def test_get_consent_cache_hit(client: AsyncClient):
    cache_key = f"consent:{USER_ID}:{PURPOSE}"
    payload = {
        "user_id": USER_ID,
        "purpose": PURPOSE,
        "status": "granted",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }
    client.fake_redis._store[cache_key] = json.dumps(payload)  # type: ignore[attr-defined]

    response = await client.get(f"/consent/{USER_ID}/{PURPOSE}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "granted"
    assert body["cached"] is True


# ── GET /consent — 404 when no record ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_consent_not_found(client: AsyncClient):
    client.fake_pool.rows = []  # type: ignore[attr-defined]

    response = await client.get(f"/consent/{USER_ID}/nonexistent_purpose")
    assert response.status_code == 404


# ── POST /consent/revoke ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_revoke_consent(client: AsyncClient):
    revoked_row = {**FAKE_ROW, "status": "revoked"}
    client.fake_pool.rows = [revoked_row]  # type: ignore[attr-defined]

    response = await client.post(
        "/consent/revoke",
        json={"user_id": USER_ID, "purpose": PURPOSE},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "revoked"


# ── POST /consent/revoke — 404 when no record ─────────────────────────────────

@pytest.mark.asyncio
async def test_revoke_consent_not_found(client: AsyncClient):
    client.fake_pool.rows = []  # type: ignore[attr-defined]

    response = await client.post(
        "/consent/revoke",
        json={"user_id": USER_ID, "purpose": "nonexistent"},
    )
    assert response.status_code == 404
