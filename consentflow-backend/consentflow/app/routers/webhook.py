"""
routers/webhook.py — Webhook ingress for external consent-revocation signals.

Endpoint
--------
POST /webhook/consent-revoke

Accepts an OneTrust-style payload, applies the revocation to the DB and Redis
cache (reusing the existing consent logic), then publishes a Kafka event so
every downstream pipeline stage can react in real time.

Idempotency
-----------
Duplicate webhooks for the same user+purpose are safe: the DB upsert always
sets status='revoked' and the cache is always invalidated.  If no prior
consent record exists, one is created implicitly via an INSERT … ON CONFLICT
upsert so the endpoint never returns 404 for an unknown user+purpose pair.

Error handling
--------------
- DB or cache failure  → 500
- Kafka publish failure → 207 Multi-Status (DB+cache update still committed)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from consentflow.app.cache import invalidate_consent_cache
from consentflow.app.kafka_producer import publish_revocation
from consentflow.memory_store import memory_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


# ── Pydantic v2 models ─────────────────────────────────────────────────────────


class OneTrustRevokePayload(BaseModel):
    """
    Mock OneTrust consent-revocation webhook payload.

    OneTrust sends camelCase fields; we alias them to snake_case internally.
    """

    model_config = {"populate_by_name": True}

    userId: str = Field(
        ...,
        description="UUID of the user whose consent is being revoked",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    purpose: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Processing purpose being revoked (e.g. 'analytics')",
        examples=["analytics"],
    )
    consentStatus: str = Field(
        ...,
        description="Must be 'revoked' for this endpoint",
        examples=["revoked"],
    )
    timestamp: str = Field(
        ...,
        description="ISO-8601 UTC timestamp of the revocation event",
        examples=["2024-07-15T10:30:00Z"],
    )


class WebhookRevokeResponse(BaseModel):
    status: str
    user_id: str
    purpose: str
    kafka_published: bool = True
    warning: str | None = None


# ── Dependency helpers ─────────────────────────────────────────────────────────


def _get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool  # type: ignore[no-any-return]


def _get_redis(request: Request):
    return request.app.state.redis_client


def _get_producer(request: Request) -> AIOKafkaProducer:
    return request.app.state.kafka_producer  # type: ignore[no-any-return]


# ── Core revocation logic (reused by the HTTP endpoint) ───────────────────────


async def _apply_revocation_to_db(
    pool: asyncpg.Pool,
    user_id: UUID,
    purpose: str,
) -> None:
    """
    Upsert a 'revoked' record in the DB for user+purpose.

    Uses INSERT … ON CONFLICT so the operation is idempotent:
    - If a record already exists → status and updated_at are updated.
    - If no record exists        → a new row is inserted with a synthetic
      data_type of 'webhook' (we have no data_type in the OneTrust payload).

    This intentionally does NOT raise 404 when there is no prior record,
    making the endpoint fully idempotent for duplicate webhook deliveries.
    """
    sql = """
        INSERT INTO consent_records (user_id, data_type, purpose, status, updated_at)
        VALUES ($1, 'webhook', $2, 'revoked', NOW())
        ON CONFLICT (user_id, purpose, data_type)
        DO UPDATE SET
            status     = 'revoked',
            updated_at = NOW()
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(sql, user_id, purpose)
    except asyncpg.PostgresError as exc:
        logger.error(
            "DB error during webhook revocation — user_id=%s purpose=%s error=%s",
            user_id,
            purpose,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while applying revocation.",
        )


# ── POST /webhook/consent-revoke ───────────────────────────────────────────────


@router.post(
    "/consent-revoke",
    response_model=WebhookRevokeResponse,
    # 200 on full success, but we may return 207 if Kafka fails.
    # FastAPI doesn't natively support conditional status codes in the
    # decorator, so we use a JSONResponse inside the handler when needed.
    status_code=status.HTTP_200_OK,
    summary="Receive a consent-revocation webhook",
    description=(
        "Accepts an OneTrust-style consent-revocation signal. "
        "Applies the revocation to the DB, invalidates the Redis cache entry, "
        "and publishes a `consent.revoked` event to Kafka. "
        "This endpoint is **idempotent** — duplicate payloads for the same "
        "user+purpose are safe and will not produce errors."
    ),
    responses={
        200: {"description": "Revocation fully propagated (DB + cache + Kafka)"},
        207: {"description": "DB+cache updated but Kafka publish failed"},
        422: {"description": "Invalid payload"},
        500: {"description": "Database error"},
    },
)
async def receive_consent_revoke(
    body: OneTrustRevokePayload,
    request: Request,
) -> WebhookRevokeResponse:
    pool = _get_pool(request)
    redis = _get_redis(request)
    producer = _get_producer(request)

    # ── 1. Validate that the incoming status is actually a revocation ──────────
    if body.consentStatus.lower() != "revoked":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unexpected consentStatus='{body.consentStatus}'. "
                "This endpoint only handles revocations."
            ),
        )

    # ── 2. Parse user_id ──────────────────────────────────────────────────────
    try:
        user_uuid = UUID(body.userId)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"userId='{body.userId}' is not a valid UUID.",
        )

    logger.info(
        "Webhook received — user_id=%s purpose=%s timestamp=%s",
        user_uuid,
        body.purpose,
        body.timestamp,
    )

    # ── 3. Persist revocation to DB (idempotent upsert) ───────────────────────
    await _apply_revocation_to_db(pool, user_uuid, body.purpose)

    # ── 4. Invalidate Redis cache ─────────────────────────────────────────────
    await invalidate_consent_cache(redis, user_uuid, body.purpose)

    # ── 5. Publish Kafka event ────────────────────────────────────────────────
    kafka_ok = True
    warning: str | None = None

    try:
        await publish_revocation(
            producer=producer,
            user_id=str(user_uuid),
            purpose=body.purpose,
            timestamp=body.timestamp,
        )
    except KafkaError as exc:
        kafka_ok = False
        warning = f"Kafka publish failed: {exc}. DB and cache have been updated."
        logger.warning(
            "Webhook: DB+cache updated but Kafka failed — user_id=%s purpose=%s error=%s",
            user_uuid,
            body.purpose,
            exc,
        )

    # ── 6. Write freeze log (Plan 1.6) ────────────────────────────────────────
    # Record the memory count at the exact moment of revocation so the frontend
    # can display "2 facts (frozen forever)" correctly.
    try:
        memory_count = await memory_store.get_memory_count(pool, str(user_uuid))
        await pool.execute(
            """
            INSERT INTO consent_freeze_log (user_id, frozen_at_count)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE
            SET frozen_at_count = $2,
                frozen_at       = NOW()
            """,
            user_uuid,
            memory_count,
        )
        logger.info(
            "Freeze log written — user_id=%s memory_count=%d",
            body.userId,
            memory_count,
        )
    except Exception as exc:  # noqa: BLE001
        # Non-critical: log and continue — the revocation itself already succeeded
        logger.warning("Freeze log write failed for user %s: %s", body.userId, exc)

    # ── 7. Build response ─────────────────────────────────────────────────────
    response_body = WebhookRevokeResponse(
        status="propagated" if kafka_ok else "partial",
        user_id=str(user_uuid),
        purpose=body.purpose,
        kafka_published=kafka_ok,
        warning=warning,
    )

    if not kafka_ok:
        # Return 207 Multi-Status to signal partial success
        from fastapi.responses import JSONResponse

        return JSONResponse(  # type: ignore[return-value]
            status_code=status.HTTP_207_MULTI_STATUS,
            content=response_body.model_dump(),
        )

    return response_body
