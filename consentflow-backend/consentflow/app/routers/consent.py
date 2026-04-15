"""
routers/consent.py — Consent CRUD endpoints.

Endpoints
---------
POST   /consent                  — upsert a consent record
GET    /consent/{user_id}/{purpose} — current status (Redis-cached)
POST   /consent/revoke           — revoke consent for user+purpose
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, List
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from consentflow.app.cache import (
    get_consent_cache,
    invalidate_consent_cache,
    set_consent_cache,
)
from consentflow.app.models import (
    ConsentRecord,
    ConsentRevokeRequest,
    ConsentStatus,
    ConsentStatusResponse,
    ConsentUpsertRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consent", tags=["consent"])


# ── Dependency helpers ─────────────────────────────────────────────────────────

def _get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool


def _get_redis(request: Request):
    return request.app.state.redis_client


# ── GET /consent ──────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=List[ConsentRecord],
    status_code=status.HTTP_200_OK,
    summary="List all consent records",
    description="Returns the 1000 most recent consent records across all users.",
)
async def list_consents(
    pool: asyncpg.Pool = Depends(_get_pool),
) -> List[ConsentRecord]:
    sql = """
        SELECT id, user_id, data_type, purpose, status, updated_at
        FROM consent_records
        ORDER BY updated_at DESC
        LIMIT 1000
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)
    except asyncpg.PostgresError as exc:
        logger.error("DB error listing consents: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    return [
        ConsentRecord(
            id=row["id"],
            user_id=row["user_id"],
            data_type=row["data_type"],
            purpose=row["purpose"],
            status=ConsentStatus(row["status"]),
            updated_at=row["updated_at"],
        )
        for row in rows
    ]

# ── POST /consent ──────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ConsentRecord,
    status_code=status.HTTP_200_OK,
    summary="Upsert a consent record",
    description=(
        "Creates or updates the consent record for a given user, data_type, "
        "and purpose. On conflict (same user+purpose+data_type) the existing "
        "row is updated in-place."
    ),
)
async def upsert_consent(
    body: ConsentUpsertRequest,
    pool: asyncpg.Pool = Depends(_get_pool),
    redis=Depends(_get_redis),
) -> ConsentRecord:
    sql = """
        INSERT INTO consent_records (user_id, data_type, purpose, status, updated_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (user_id, purpose, data_type)
        DO UPDATE SET
            status     = EXCLUDED.status,
            updated_at = EXCLUDED.updated_at
        RETURNING id, user_id, data_type, purpose, status, updated_at
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                body.user_id,
                body.data_type,
                body.purpose,
                body.status.value,
            )
            
            # If consent is granted, clear the freeze log to unfreeze the memory bank
            if body.status.value == "granted":
                await conn.execute(
                    "DELETE FROM consent_freeze_log WHERE user_id = $1", 
                    str(body.user_id)
                )
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {body.user_id} does not exist.",
        )
    except asyncpg.PostgresError as exc:
        logger.error("DB error on upsert: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    # Invalidate cache after any write
    await invalidate_consent_cache(redis, body.user_id, body.purpose)

    return ConsentRecord(
        id=row["id"],
        user_id=row["user_id"],
        data_type=row["data_type"],
        purpose=row["purpose"],
        status=ConsentStatus(row["status"]),
        updated_at=row["updated_at"],
    )


# ── POST /consent/revoke ───────────────────────────────────────────────────────

@router.post(
    "/revoke",
    response_model=ConsentRecord,
    status_code=status.HTTP_200_OK,
    summary="Revoke consent for a user+purpose",
    description=(
        "Sets status='revoked' for ALL data_type rows matching the given "
        "user_id and purpose, and invalidates the Redis cache entry."
    ),
)
async def revoke_consent(
    body: ConsentRevokeRequest,
    pool: asyncpg.Pool = Depends(_get_pool),
    redis=Depends(_get_redis),
) -> ConsentRecord:
    # We update every data_type under this user+purpose pair and return the
    # most-recently updated row so the caller can confirm the action.
    sql = """
        UPDATE consent_records
           SET status     = 'revoked',
               updated_at = NOW()
         WHERE user_id = $1
           AND purpose = $2
     RETURNING id, user_id, data_type, purpose, status, updated_at
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, body.user_id, body.purpose)

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No consent records found for user={body.user_id} "
                f"purpose='{body.purpose}'."
            ),
        )

    # Invalidate cache
    await invalidate_consent_cache(redis, body.user_id, body.purpose)

    # Return the most recently updated row (last in the result set)
    row = rows[-1]
    return ConsentRecord(
        id=row["id"],
        user_id=row["user_id"],
        data_type=row["data_type"],
        purpose=row["purpose"],
        status=ConsentStatus(row["status"]),
        updated_at=row["updated_at"],
    )


# ── GET /consent/{user_id}/{purpose} ──────────────────────────────────────────

@router.get(
    "/{user_id}/{purpose}",
    response_model=ConsentStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current consent status",
    description=(
        "Returns the effective consent status for a user+purpose pair. "
        "Results are served from Redis (TTL 60 s) when available."
    ),
)
async def get_consent_status(
    user_id: UUID,
    purpose: str,
    pool: asyncpg.Pool = Depends(_get_pool),
    redis=Depends(_get_redis),
) -> ConsentStatusResponse:
    # 1. Redis cache check
    cached = await get_consent_cache(redis, user_id, purpose)
    if cached:
        return ConsentStatusResponse(
            user_id=UUID(cached["user_id"]),
            purpose=cached["purpose"],
            status=ConsentStatus(cached["status"]),
            updated_at=datetime.fromisoformat(cached["updated_at"]),
            cached=True,
        )

    # 2. Postgres fallback — most recently updated record for this user+purpose
    sql = """
        SELECT user_id, purpose, status, updated_at
          FROM consent_records
         WHERE user_id = $1
           AND purpose = $2
         ORDER BY updated_at DESC
         LIMIT 1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, user_id, purpose)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No consent record found for user={user_id} "
                f"purpose='{purpose}'."
            ),
        )

    payload = {
        "user_id": str(row["user_id"]),
        "purpose": row["purpose"],
        "status": row["status"],
        "updated_at": row["updated_at"].isoformat(),
    }

    # 3. Populate cache for subsequent reads
    await set_consent_cache(redis, user_id, purpose, payload)

    return ConsentStatusResponse(
        user_id=row["user_id"],
        purpose=row["purpose"],
        status=ConsentStatus(row["status"]),
        updated_at=row["updated_at"],
        cached=False,
    )
