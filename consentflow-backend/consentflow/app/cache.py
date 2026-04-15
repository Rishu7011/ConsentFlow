"""
cache.py — Redis helpers for consent lookup caching.

Key schema:  consent:{user_id}:{purpose}
TTL:         settings.consent_cache_ttl (default 60 s)
"""
from __future__ import annotations

import json
import logging
from uuid import UUID

import redis.asyncio as aioredis
from redis.asyncio import Redis

from consentflow.app.config import settings

logger = logging.getLogger(__name__)

# ── Key helpers ────────────────────────────────────────────────────────────────

def _consent_key(user_id: UUID | str, purpose: str) -> str:
    return f"consent:{user_id}:{purpose}"


# ── Lifecycle ──────────────────────────────────────────────────────────────────

async def create_redis_client() -> Redis:
    client: Redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
    )
    # Validate connection immediately
    await client.ping()
    logger.info("Redis client connected: %s", settings.redis_url)
    return client


async def close_redis_client(client: Redis) -> None:
    await client.aclose()
    logger.info("Redis client closed")


async def check_redis(client: Redis) -> str:
    """Ping Redis; return 'ok' or an error string."""
    try:
        await client.ping()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.error("Redis health-check failed: %s", exc)
        return f"error: {exc}"


# ── Read / Write ───────────────────────────────────────────────────────────────

async def get_consent_cache(
    client: Redis,
    user_id: UUID | str,
    purpose: str,
) -> dict | None:
    """
    Return the cached consent payload as a dict, or None on cache miss.
    """
    key = _consent_key(user_id, purpose)
    try:
        raw = await client.get(key)
        if raw is None:
            return None
        logger.debug("Cache HIT  key=%s", key)
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        # Never let a cache failure break the request path
        logger.warning("Cache GET failed for key=%s: %s", key, exc)
        return None


async def set_consent_cache(
    client: Redis,
    user_id: UUID | str,
    purpose: str,
    payload: dict,
    ttl: int | None = None,
) -> None:
    """
    Store the consent payload in Redis with TTL.
    `payload` must be JSON-serialisable.
    """
    key = _consent_key(user_id, purpose)
    ttl = ttl if ttl is not None else settings.consent_cache_ttl
    try:
        await client.set(key, json.dumps(payload, default=str), ex=ttl)
        logger.debug("Cache SET  key=%s  ttl=%ds", key, ttl)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cache SET failed for key=%s: %s", key, exc)


async def invalidate_consent_cache(
    client: Redis,
    user_id: UUID | str,
    purpose: str,
) -> None:
    """Delete the cached consent entry for user+purpose."""
    key = _consent_key(user_id, purpose)
    try:
        deleted = await client.delete(key)
        logger.debug("Cache INVALIDATE key=%s  deleted=%d", key, deleted)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cache DELETE failed for key=%s: %s", key, exc)
