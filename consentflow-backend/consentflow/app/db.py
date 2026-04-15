"""
db.py — asyncpg connection pool management.

The pool is stored on the FastAPI `app.state` object so it is accessible
throughout the request lifecycle without globals.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from asyncpg import Pool

from consentflow.app.config import settings

logger = logging.getLogger(__name__)


async def create_pool() -> Pool:
    """Create and return an asyncpg connection pool."""
    pool: Pool = await asyncpg.create_pool(
        dsn=settings.asyncpg_dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
        statement_cache_size=0,   # safe default for pgBouncer compatibility
    )
    logger.info("PostgreSQL connection pool created (min=2, max=10)")
    return pool


async def close_pool(pool: Pool) -> None:
    """Gracefully close all connections in the pool."""
    await pool.close()
    logger.info("PostgreSQL connection pool closed")


async def check_postgres(pool: Pool) -> str:
    """Ping Postgres; return 'ok' or error string."""
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.error("Postgres health-check failed: %s", exc)
        return f"error: {exc}"
