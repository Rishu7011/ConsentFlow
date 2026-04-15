"""
tests/conftest.py — shared pytest fixtures for ConsentFlow.

Strategy: override `app.router.lifespan_context` with a no-op that injects
the in-memory fakes directly into app.state. This runs before any request
is handled, so all state is in place when the router runs.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ── In-memory fakes ────────────────────────────────────────────────────────────

class FakeConnection:
    """Minimal asyncpg connection stub."""

    def __init__(self, rows: list):
        self._rows = rows

    async def fetchrow(self, *args, **kwargs):
        return self._rows[0] if self._rows else None

    async def fetch(self, *args, **kwargs):
        return self._rows

    async def execute(self, *args, **kwargs):
        return None

    async def fetchval(self, *args, **kwargs):
        return 1


class FakePool:
    """Minimal asyncpg Pool stub."""

    def __init__(self):
        self.rows: list = []

    def acquire(self):
        return self

    async def __aenter__(self):
        return FakeConnection(self.rows)

    async def __aexit__(self, *args):
        pass

    async def close(self):
        pass


class FakeRedis:
    """In-memory Redis stub."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value, ex: int | None = None):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)
        return 1

    async def ping(self):
        return True

    async def aclose(self):
        pass


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_pool() -> FakePool:
    return FakePool()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest_asyncio.fixture
async def client(fake_pool: FakePool, fake_redis: FakeRedis) -> AsyncGenerator[AsyncClient, None]:
    """
    ASGI test client with fakes injected directly into app state.
    ASGITransport does not trigger FastAPI lifespan by default, so we
    manually set the state properties that the lifespan would normally create.
    """
    from consentflow.app.main import app
    
    app.state.db_pool = fake_pool
    app.state.redis_client = fake_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.fake_pool = fake_pool      # type: ignore[attr-defined]
        ac.fake_redis = fake_redis    # type: ignore[attr-defined]
        yield ac
