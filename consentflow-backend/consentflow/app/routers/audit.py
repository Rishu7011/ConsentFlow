"""
routers/audit.py — Audit trail endpoint (Step 7).

Endpoint
--------
GET /audit/trail

Returns a structured log of consent enforcement actions taken by the four
pipeline gates (dataset, inference, training, monitoring).  Records are
inserted into the ``audit_log`` table by the OTel gate wrappers at gate-call
time.

Query parameters
----------------
user_id:   Filter to actions for a specific user (optional).
gate_name: Filter to a specific gate (optional).
limit:     Maximum number of rows to return (default 100, max 1000).

Response
--------
``AuditTrailResponse`` with ``entries`` list and ``total`` count.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request

from consentflow.app.models import AuditLogEntry, AuditTrailResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["observability"])


# ── Dependency helpers ─────────────────────────────────────────────────────────


def _get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool  # type: ignore[no-any-return]


# ── GET /audit/trail ───────────────────────────────────────────────────────────


@router.get(
    "/trail",
    response_model=AuditTrailResponse,
    status_code=200,
    summary="Consent audit trail",
    description=(
        "Returns a time-ordered log of consent enforcement actions taken by each "
        "pipeline gate.  Optionally filter by ``user_id`` or ``gate_name``. "
        "Results are ordered newest-first, capped at ``limit`` rows (max 1000)."
    ),
    responses={
        200: {"description": "Audit trail returned"},
        500: {"description": "Database error"},
    },
)
async def get_audit_trail(
    user_id: str | None = Query(default=None, description="Filter by user_id"),
    gate_name: str | None = Query(
        default=None,
        description="Filter by gate name (dataset_gate | inference_gate | training_gate | monitoring_gate)",
    ),
    limit: int = Query(default=100, ge=1, le=1000, description="Max rows to return"),
    pool: asyncpg.Pool = Depends(_get_pool),
) -> AuditTrailResponse:
    """Return time-ordered consent audit trail with optional filters."""

    # ── Build dynamic WHERE clause ────────────────────────────────────────────
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if user_id is not None:
        conditions.append(f"user_id = ${idx}")
        params.append(user_id)
        idx += 1

    if gate_name is not None:
        conditions.append(f"gate_name = ${idx}")
        params.append(gate_name)
        idx += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # ── Count query ───────────────────────────────────────────────────────────
    count_sql = f"SELECT COUNT(*) FROM audit_log {where_clause}"

    # ── Data query ────────────────────────────────────────────────────────────
    params_with_limit = params + [limit]
    data_sql = f"""
        SELECT id, event_time, user_id, gate_name, action_taken,
               consent_status, purpose, metadata, trace_id
          FROM audit_log
         {where_clause}
         ORDER BY event_time DESC
         LIMIT ${idx}
    """

    async with pool.acquire() as conn:
        total: int = await conn.fetchval(count_sql, *params)
        rows = await conn.fetch(data_sql, *params_with_limit)

    entries: list[AuditLogEntry] = []
    for row in rows:
        # asyncpg returns JSONB as a string — parse it
        meta = row["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = None

        entries.append(
            AuditLogEntry(
                id=UUID(str(row["id"])),
                event_time=row["event_time"],
                user_id=row["user_id"],
                gate_name=row["gate_name"],
                action_taken=row["action_taken"],
                consent_status=row["consent_status"],
                purpose=row["purpose"],
                metadata=meta,
                trace_id=row["trace_id"],
            )
        )

    logger.info(
        "audit/trail — returned %d/%d rows  user_id=%s  gate=%s",
        len(entries),
        total,
        user_id,
        gate_name,
    )
    return AuditTrailResponse(entries=entries, total=total)
