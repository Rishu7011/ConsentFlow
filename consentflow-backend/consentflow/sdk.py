"""
consentflow/sdk.py — Reusable consent-check SDK.

Public API
----------
is_user_consented(user_id, purpose, *, redis_client=None, db_pool=None) -> bool

Priority
--------
1. Redis cache — key: ``consent:{user_id}:{purpose}``   (fast path, ~1 ms)
2. PostgreSQL  — ``consent_records`` table               (authoritative source)
3. Default to ``False`` (deny) if no record exists

Sync callers
------------
`is_user_consented_sync()` wraps the async version with `asyncio.run()` so
scripts and notebooks can use it without an existing event loop.  Inside an
already-running loop (e.g. inside FastAPI or pytest-asyncio) prefer the async
variant directly.

Connection management
---------------------
When ``redis_client`` / ``db_pool`` are *not* supplied the SDK creates short-
lived connections and tears them down after the call.  For high-throughput use
supply shared pool/client instances.
"""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import asyncpg
import redis.asyncio as aioredis
from redis.asyncio import Redis

from consentflow.app.config import settings

logger = logging.getLogger(__name__)

# ── Internal helpers ───────────────────────────────────────────────────────────


def _consent_key(user_id: str, purpose: str) -> str:
    return f"consent:{user_id}:{purpose}"


async def _check_redis(client: Redis, user_id: str, purpose: str) -> bool | None:
    """
    Try to read consent status from Redis.

    Returns
    -------
    True   — cached status is 'granted'
    False  — cached status is 'revoked'
    None   — cache miss (key not found or read error)
    """
    key = _consent_key(user_id, purpose)
    try:
        raw = await client.get(key)
        if raw is None:
            logger.debug("SDK cache MISS  key=%s", key)
            return None
        import json
        payload = json.loads(raw)
        result = payload.get("status") == "granted"
        logger.debug("SDK cache HIT   key=%s  granted=%s", key, result)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("SDK Redis read error key=%s: %s", key, exc)
        return None


async def _check_postgres(pool: asyncpg.Pool, user_id: str, purpose: str) -> bool:
    """
    Query PostgreSQL for the most-recent consent record.

    Returns ``True`` iff the latest record has status='granted'.
    Returns ``False`` when no record exists (deny-by-default).
    """
    sql = """
        SELECT status
          FROM consent_records
         WHERE user_id = $1::uuid
           AND purpose = $2
         ORDER BY updated_at DESC
         LIMIT 1
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, user_id, purpose)
        if row is None:
            logger.debug("SDK DB MISS     user_id=%s purpose=%s — deny by default", user_id, purpose)
            return False
        result = row["status"] == "granted"
        logger.debug("SDK DB HIT      user_id=%s purpose=%s  granted=%s", user_id, purpose, result)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("SDK Postgres read error user_id=%s purpose=%s: %s", user_id, purpose, exc)
        return False  # safe default


# ── Public async API ───────────────────────────────────────────────────────────


async def is_user_consented(
    user_id: str | UUID,
    purpose: str,
    *,
    redis_client: Redis | None = None,
    db_pool: asyncpg.Pool | None = None,
) -> bool:
    """
    Return ``True`` iff the user has an active 'granted' consent for *purpose*.

    Resolution order
    ----------------
    1. Redis cache (sub-millisecond)
    2. PostgreSQL  (authoritative)
    3. ``False``   (deny-by-default when no record found)

    Parameters
    ----------
    user_id:      User UUID (str or UUID).
    purpose:      Consent purpose string, e.g. ``'analytics'``.
    redis_client: Optional shared Redis client.  Created ad-hoc if omitted.
    db_pool:      Optional shared asyncpg pool.  Created ad-hoc if omitted.
    """
    uid = str(user_id)

    # ── 1. Redis ──────────────────────────────────────────────────────────────
    _own_redis = redis_client is None
    if _own_redis:
        redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
        )
    try:
        cached = await _check_redis(redis_client, uid, purpose)
        if cached is not None:
            return cached
    finally:
        if _own_redis:
            await redis_client.aclose()

    # ── 2. PostgreSQL fallback ────────────────────────────────────────────────
    _own_pool = db_pool is None
    if _own_pool:
        db_pool = await asyncpg.create_pool(
            dsn=settings.asyncpg_dsn,
            min_size=1,
            max_size=3,
            command_timeout=10,
            statement_cache_size=0,
        )
    try:
        return await _check_postgres(db_pool, uid, purpose)
    finally:
        if _own_pool and db_pool is not None:
            await db_pool.close()


def is_user_consented_sync(
    user_id: str | UUID,
    purpose: str,
    *,
    redis_client: Redis | None = None,
    db_pool: asyncpg.Pool | None = None,
) -> bool:
    """
    Synchronous wrapper around :func:`is_user_consented`.

    Suitable for scripts, notebooks, and non-async contexts.
    Do **not** call from within a running event loop (use ``await is_user_consented(...)``
    instead, or use ``asyncio.get_event_loop().run_until_complete(...)``).
    """
    return asyncio.run(
        is_user_consented(
            user_id,
            purpose,
            redis_client=redis_client,
            db_pool=db_pool,
        )
    )
