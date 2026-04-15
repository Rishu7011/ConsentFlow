"""
routers/chat.py — The heart of the ConsentFlow demo.

Plan 1.5

Endpoints
---------
POST   /chat/message              — RAG chat with Gemini + Presidio PII scan
GET    /chat/state/{user_id}      — memory state + frozen status
DELETE /chat/state/{user_id}      — demo reset (clears all memory + history)
GET    /chat/history              — paginated chat log

Flow for POST /chat/message
---------------------------
1. Presidio PII scan  (always — before and after revocation)
2. Check consent      (Redis → Postgres fallback)
3. Memory update      (only if consent granted)
4. Retrieve memories  (always — returns frozen set after revocation)
5. Call Gemini        (always)
6. Log to chat_log
7. Log to audit_log
8. Read freeze state
9. Return response
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from presidio_anonymizer.entities import OperatorConfig
from consentflow.anonymizer import ALL_PII_ENTITIES, analyzer, anonymizer
from consentflow.app.cache import get_consent_cache, set_consent_cache
from consentflow.gemini_client import gemini_client
from consentflow.memory_store import memory_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

_PURPOSE = "model_training"


# ── Dependency helpers ─────────────────────────────────────────────────────────


def _get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool  # type: ignore[no-any-return]


def _get_redis(request: Request):
    return request.app.state.redis_client


# ── Pydantic models ────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="User UUID")
    message: str = Field(..., min_length=1, max_length=4096, description="User message")


class MemoryState(BaseModel):
    user_id: str
    memories: list[str]
    memory_count: int
    frozen: bool
    frozen_at_count: int | None


class ChatResponse(BaseModel):
    reply: str
    trained_on_message: bool
    consent_status: str
    pii_detected: list[str]
    message_redacted: str
    memories_used: list[str]
    memory_state: MemoryState


class ChatHistoryEntry(BaseModel):
    id: str
    event_time: str
    user_id: str
    message: str
    message_redacted: str
    reply: str
    trained: bool
    memory_used: list[str]
    pii_detected: list[str]
    consent_status: str


class ChatHistoryResponse(BaseModel):
    entries: list[ChatHistoryEntry]
    total: int


class ChatStateResponse(BaseModel):
    user_id: str
    memories: list[str]
    memory_count: int
    frozen: bool
    frozen_at_count: int | None
    consent_status: str


class ChatResetResponse(BaseModel):
    reset: bool


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _resolve_consent(pool: asyncpg.Pool, redis: Any, user_id: str) -> str:
    """
    Return "granted" or "revoked" for purpose=model_training.

    Check order:
      1. Redis cache  (key: consent:{user_id}:model_training)
      2. Postgres     (most recent row for user + purpose)
      3. Default      → "revoked" (fail-closed)
    """
    # 1. Redis
    cached = await get_consent_cache(redis, user_id, _PURPOSE)
    if cached:
        return cached.get("status", "revoked")

    # 2. Postgres
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT status, updated_at FROM consent_records
                WHERE  user_id::text = $1
                  AND  purpose = $2
                ORDER  BY updated_at DESC
                LIMIT  1
                """,
                user_id,
                _PURPOSE,
            )
        if row:
            consent_status_val = row["status"]
            # Write back to Redis so future requests hit cache, not Postgres
            await set_consent_cache(
                redis,
                user_id,
                _PURPOSE,
                {
                    "user_id": user_id,
                    "purpose": _PURPOSE,
                    "status": consent_status_val,
                    "updated_at": row["updated_at"].isoformat(),
                },
            )
            return consent_status_val
    except Exception as exc:  # noqa: BLE001
        logger.warning("Consent DB lookup failed for user %s: %s", user_id, exc)

    # 3. Fail-closed
    return "revoked"


async def _get_freeze_state(
    pool: asyncpg.Pool, user_id: str
) -> tuple[bool, int | None]:
    """
    Returns (frozen: bool, frozen_at_count: int | None).
    Frozen = a row exists in consent_freeze_log for this user_id.
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT frozen_at_count FROM consent_freeze_log WHERE user_id = $1",
                user_id,
            )
        if row:
            return True, int(row["frozen_at_count"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("freeze state lookup failed for user %s: %s", user_id, exc)
    return False, None


async def _log_audit(
    pool: asyncpg.Pool,
    user_id: str,
    action_taken: str,
    consent_status: str,
    metadata: dict[str, Any],
) -> None:
    """Append a row to audit_log for the training_gate."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log
                    (user_id, gate_name, action_taken, consent_status, purpose, metadata)
                VALUES ($1, 'training_gate', $2, $3, $4, $5)
                """,
                user_id,
                action_taken,
                consent_status,
                _PURPOSE,
                json.dumps(metadata),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_log insert failed: %s", exc)


# ── POST /chat/message ─────────────────────────────────────────────────────────


@router.post(
    "/message",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a chat message",
    description=(
        "Scans the message for PII via Presidio, checks consent, "
        "optionally stores facts in the RAG memory store, calls Gemini, "
        "and logs the exchange."
    ),
)
async def chat_message(
    body: ChatRequest,
    request: Request,
    pool: asyncpg.Pool = Depends(_get_pool),
    redis=Depends(_get_redis),
) -> ChatResponse:
    user_id = body.user_id
    message = body.message

    # ── 1. Presidio PII scan ──────────────────────────────────────────────────
    analyzer_results = analyzer.analyze(
        text=message,
        language="en",
        entities=ALL_PII_ENTITIES,
    )
    # For redaction: use all results (even low-confidence) to be safe
    # For memory tagging: only use high-confidence results (≥ 0.7) to avoid
    # false positives (e.g. a name mis-tagged as IN_PAN)
    _MIN_SCORE = 0.7
    pii_entities: list[str] = [
        r.entity_type for r in analyzer_results if r.score >= _MIN_SCORE
    ]
    # Deduplicate while preserving order
    _seen: set[str] = set()
    pii_entities = [e for e in pii_entities if not (e in _seen or _seen.add(e))]

    if analyzer_results:
        message_redacted = anonymizer.anonymize(
            text=message,
            analyzer_results=analyzer_results,
            operators={"DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"})}
        ).text
    else:
        message_redacted = message

    logger.debug("PII scan — user=%s entities=%s", user_id, pii_entities)

    # ── 2. Check consent ──────────────────────────────────────────────────────
    consent_status = await _resolve_consent(pool, redis, user_id)
    consent_granted = consent_status == "granted"

    # ── 3. Memory update (only if consent granted) ────────────────────────────
    if consent_granted:
        stored = await memory_store.extract_and_store(pool, user_id, message, pii_entities)
        trained = True
    else:
        stored = []
        trained = False

    # ── 4. Retrieve memories (always — frozen set returned after revocation) ──
    memories = await memory_store.get_memories(pool, user_id)

    # ── 5. Call Gemini ────────────────────────────────────────────────────────
    gemini_prompt = message if consent_granted else message_redacted
    reply = await gemini_client.chat(memories, gemini_prompt)

    # ── 6. Log to chat_log ────────────────────────────────────────────────────
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_log
                    (user_id, message, message_redacted, reply, trained,
                     memory_used, pii_detected, consent_status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                user_id,
                message if consent_granted else message_redacted,
                message_redacted,
                reply,
                trained,
                memories,
                pii_entities,
                consent_status,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat_log insert failed: %s", exc)

    # ── 7. Log to audit_log ───────────────────────────────────────────────────
    action_taken = "memory_stored" if trained else "memory_blocked"
    await _log_audit(
        pool,
        user_id,
        action_taken,
        consent_status,
        {
            "pii_detected": pii_entities,
            "pii_redacted": message != message_redacted,
            "memories_used": len(memories),
            "message_redacted": message_redacted,
        },
    )

    # ── 8. Get freeze state ───────────────────────────────────────────────────
    frozen, frozen_at_count = await _get_freeze_state(pool, user_id)

    # ── 9. Return ─────────────────────────────────────────────────────────────
    return ChatResponse(
        reply=reply,
        trained_on_message=trained,
        consent_status=consent_status,
        pii_detected=pii_entities,
        message_redacted=message_redacted,
        memories_used=memories,
        memory_state=MemoryState(
            user_id=user_id,
            memories=memories,
            memory_count=len(memories),
            frozen=frozen,
            frozen_at_count=frozen_at_count,
        ),
    )


# ── GET /chat/state/{user_id} ─────────────────────────────────────────────────


@router.get(
    "/state/{user_id}",
    response_model=ChatStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Get memory state for a user",
    description=(
        "Returns the current RAG memory state, freeze status, and consent status "
        "for the given user. Polled every 2 s by the frontend memory panel."
    ),
)
async def get_chat_state(
    user_id: str,
    pool: asyncpg.Pool = Depends(_get_pool),
    redis=Depends(_get_redis),
) -> ChatStateResponse:
    frozen, frozen_at_count = await _get_freeze_state(pool, user_id)
    consent_status = await _resolve_consent(pool, redis, user_id)
    state = await memory_store.get_state(pool, user_id, frozen, frozen_at_count)
    return ChatStateResponse(
        user_id=user_id,
        memories=state["memories"],
        memory_count=state["memory_count"],
        frozen=state["frozen"],
        frozen_at_count=state["frozen_at_count"],
        consent_status=consent_status,
    )


# ── DELETE /chat/state/{user_id} ──────────────────────────────────────────────


@router.delete(
    "/state/{user_id}",
    response_model=ChatResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset demo state for a user",
    description=(
        "Deletes all memory chunks, chat history, and the freeze log for the "
        "given user. Use this to restore the demo to its initial state."
    ),
)
async def reset_chat_state(
    user_id: str,
    pool: asyncpg.Pool = Depends(_get_pool),
) -> ChatResetResponse:
    await memory_store.clear_memories(pool, user_id)
    logger.info("Demo state reset for user %s", user_id)
    return ChatResetResponse(reset=True)


# ── GET /chat/history ─────────────────────────────────────────────────────────


@router.get(
    "/history",
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="List chat history",
    description="Returns chat_log rows ordered newest-first.",
)
async def get_chat_history(
    user_id: str | None = Query(default=None, description="Filter by user UUID"),
    limit: int = Query(default=50, ge=1, le=500, description="Max rows to return"),
    pool: asyncpg.Pool = Depends(_get_pool),
) -> ChatHistoryResponse:
    if user_id:
        sql = """
            SELECT id, event_time, user_id, message, message_redacted, reply,
                   trained, memory_used, pii_detected, consent_status
            FROM   chat_log
            WHERE  user_id::text = $1
            ORDER  BY event_time DESC
            LIMIT  $2
        """
        params: tuple[Any, ...] = (user_id, limit)
    else:
        sql = """
            SELECT id, event_time, user_id, message, message_redacted, reply,
                   trained, memory_used, pii_detected, consent_status
            FROM   chat_log
            ORDER  BY event_time DESC
            LIMIT  $1
        """
        params = (limit,)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
    except Exception as exc:  # noqa: BLE001
        logger.error("chat_log fetch failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    entries = [
        ChatHistoryEntry(
            id=str(row["id"]),
            event_time=row["event_time"].isoformat(),
            user_id=row["user_id"],
            message=row["message"],
            message_redacted=row["message_redacted"],
            reply=row["reply"],
            trained=row["trained"],
            memory_used=list(row["memory_used"] or []),
            pii_detected=list(row["pii_detected"] or []),
            consent_status=row["consent_status"],
        )
        for row in rows
    ]
    return ChatHistoryResponse(entries=entries, total=len(entries))
