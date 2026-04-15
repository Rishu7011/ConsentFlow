"""
tests/test_health.py — Smoke tests for GET /health.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["postgres"] == "ok"
    assert body["redis"] == "ok"
    assert body["status"] == "ok"
