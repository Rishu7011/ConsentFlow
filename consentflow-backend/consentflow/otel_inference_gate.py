"""
consentflow/otel_inference_gate.py — OTel-instrumented inference gate helper (Step 7).

Provides a standalone async helper ``traced_inference_check`` that records an
OTel span and writes one row to ``audit_log`` for an inference gate decision.

It is intentionally **not** another ASGI middleware — it is a pure function
that ``ConsentMiddleware.dispatch()`` can call (or tests can call directly)
with a mocked tracer, following the same injected-dependency pattern used
across Steps 3–6.

Span attributes
---------------
gate_name      : "inference_gate"
user_id        : the requesting user's ID
consent_status : "granted" | "revoked"
action_taken   : "passed" | "blocked"
path           : request path (when provided)
"""
from __future__ import annotations

import json
import logging
from typing import Any

from consentflow.telemetry import get_tracer

logger = logging.getLogger(__name__)

_GATE_NAME = "inference_gate"


async def traced_inference_check(
    user_id: str,
    consented: bool,
    *,
    path: str = "",
    purpose: str = "inference",
    tracer: Any = None,
    db_pool: Any = None,
) -> str:
    """
    Record an OTel span and audit log row for one inference gate decision.

    Parameters
    ----------
    user_id:   The requesting user's ID string.
    consented: Result of the consent check — ``True`` = granted, ``False`` = revoked.
    path:      The HTTP request path being guarded (informational).
    purpose:   Consent purpose string.
    tracer:    OTel tracer; defaults to the global tracer for this module.
    db_pool:   asyncpg pool used for audit insert; skipped if ``None``.

    Returns
    -------
    ``"passed"`` when consent is granted, ``"blocked"`` when revoked.
    """
    _tracer = tracer if tracer is not None else get_tracer(_GATE_NAME)
    action_taken = "passed" if consented else "blocked"
    consent_status = "granted" if consented else "revoked"

    with _tracer.start_as_current_span(f"{_GATE_NAME}.check") as span:
        span.set_attribute("gate_name", _GATE_NAME)
        span.set_attribute("user_id", user_id)
        span.set_attribute("consent_status", consent_status)
        span.set_attribute("action_taken", action_taken)
        span.set_attribute("path", path)
        span.set_attribute("purpose", purpose)

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
            action_taken=action_taken,
            consent_status=consent_status,
            purpose=purpose,
            metadata={"path": path} if path else None,
            trace_id=trace_id_hex,
        )

    return action_taken


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
        logger.error("audit_log insert failed (inference_gate): %s", exc)
