"""
consentflow/otel_training_gate.py — OTel-instrumented training gate helper (Step 7).

Provides a standalone async helper ``traced_training_quarantine`` that records
an OTel span and writes one ``audit_log`` row per quarantine event emitted by
the training gate.

Usage
-----
Call ``traced_training_quarantine`` *after* ``TrainingGateConsumer`` has
produced its ``QuarantineRecord`` list, passing the user_id and the list of
quarantined MLflow run IDs.

Span attributes
---------------
gate_name           : "training_gate"
user_id             : revoked user's ID
consent_status      : "revoked" (always — training gate only fires on revocation)
action_taken        : "quarantined"
quarantined_run_count: number of MLflow runs flagged
"""
from __future__ import annotations

import json
import logging
from typing import Any

from consentflow.telemetry import get_tracer

logger = logging.getLogger(__name__)

_GATE_NAME = "training_gate"


async def traced_training_quarantine(
    user_id: str,
    run_ids: list[str],
    *,
    purpose: str = "model_training",
    tracer: Any = None,
    db_pool: Any = None,
) -> None:
    """
    Record an OTel span and audit log row for a training gate quarantine event.

    Parameters
    ----------
    user_id:  Revoked user's ID.
    run_ids:  List of MLflow run IDs that were quarantined.
    purpose:  Consent purpose string.
    tracer:   OTel tracer; defaults to the global tracer for this module.
    db_pool:  asyncpg pool used for audit insert; skipped if ``None``.
    """
    _tracer = tracer if tracer is not None else get_tracer(_GATE_NAME)

    with _tracer.start_as_current_span(f"{_GATE_NAME}.quarantine") as span:
        span.set_attribute("gate_name", _GATE_NAME)
        span.set_attribute("user_id", user_id)
        span.set_attribute("consent_status", "revoked")
        span.set_attribute("action_taken", "quarantined")
        span.set_attribute("purpose", purpose)
        span.set_attribute("quarantined_run_count", len(run_ids))

        # Capture OTel trace ID
        trace_id_hex: str | None = None
        try:
            from opentelemetry import trace as otel_trace  # noqa: PLC0415
            ctx = span.get_span_context()
            if ctx and ctx.trace_id:
                trace_id_hex = format(ctx.trace_id, "032x")
        except Exception:  # noqa: BLE001
            pass

    # ── Audit log insert ──────────────────────────────────────────────────────
    if db_pool is not None:
        await _write_audit_row(
            db_pool,
            user_id=user_id,
            action_taken="quarantined",
            consent_status="revoked",
            purpose=purpose,
            metadata={"quarantined_run_ids": run_ids},
            trace_id=trace_id_hex,
        )


async def _write_audit_row(
    db_pool: Any,
    *,
    user_id: str,
    action_taken: str,
    consent_status: str,
    purpose: str | None,
    metadata: dict | None,
    trace_id: str | None,
) -> None:
    """Insert one row into ``audit_log``.  Errors are logged, never raised."""
    sql = """
        INSERT INTO audit_log
               (user_id, gate_name, action_taken, consent_status, purpose, metadata, trace_id)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
    """
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                sql,
                user_id,
                _GATE_NAME,
                action_taken,
                consent_status,
                purpose,
                json.dumps(metadata) if metadata else None,
                trace_id,
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("audit_log insert failed (training_gate): %s", exc)
