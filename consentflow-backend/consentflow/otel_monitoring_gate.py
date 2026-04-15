"""
consentflow/otel_monitoring_gate.py — OTel-instrumented monitoring gate wrapper (Step 7).

Wraps :meth:`~consentflow.monitoring_gate.ConsentAwareDriftMonitor.run_consent_aware_drift_check`
with an OpenTelemetry span and writes one ``audit_log`` row per drift check.

Design
------
* ``tracer`` is an injected parameter (default ``None`` → ``get_tracer()``).
  Tests pass a ``NonRecordingTracer`` — no OTLP endpoint required.
* ``db_pool`` is used for the audit row insert (fire-and-forget).
* The function is synchronous (like the underlying drift check) so it can be
  called from synchronous Evidently contexts without an event loop.
  The audit insert uses a thread-pool helper when called outside async context.

Span attributes
---------------
gate_name          : "monitoring_gate"
user_id            : semicolon-joined list of revoked user IDs in the window,
                     or "none" when all samples are granted
consent_status     : "revoked" | "granted"
action_taken       : "alerted" | "passed"
has_revoked_samples: bool string
alerts_fired       : number of DriftAlert objects emitted
revoked_count      : total revoked rows across all alerts
"""
from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd

from consentflow.monitoring_gate import ConsentAwareDriftMonitor, DriftCheckResult
from consentflow.telemetry import get_tracer

logger = logging.getLogger(__name__)

_GATE_NAME = "monitoring_gate"


def traced_drift_check(
    monitor: ConsentAwareDriftMonitor,
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    *,
    user_id_col: str = "user_id",
    window_start: str = "",
    window_end: str = "",
    column_mapping: Any = None,
    run_evidently: bool = True,
    tracer: Any = None,
    db_pool: Any = None,
    purpose: str = "monitoring",
) -> DriftCheckResult:
    """
    OTel-instrumented wrapper around ``run_consent_aware_drift_check``.

    Parameters
    ----------
    monitor:        :class:`~consentflow.monitoring_gate.ConsentAwareDriftMonitor`
                    instance to delegate to.
    reference_df:   Baseline dataset.
    current_df:     Current monitoring window.
    user_id_col:    Column holding user UUIDs (default: ``"user_id"``).
    window_start:   ISO-8601 window start (stored in alerts + span).
    window_end:     ISO-8601 window end.
    column_mapping: Optional Evidently ``ColumnMapping``.
    run_evidently:  Set ``False`` in tests to skip the Evidently report step.
    tracer:         OTel tracer; defaults to the global tracer for this module.
    db_pool:        asyncpg pool for audit row insert; skipped if ``None``.
    purpose:        Consent purpose string.

    Returns
    -------
    :class:`~consentflow.monitoring_gate.DriftCheckResult`
    """
    _tracer = tracer if tracer is not None else get_tracer(_GATE_NAME)

    with _tracer.start_as_current_span(f"{_GATE_NAME}.check") as span:
        span.set_attribute("gate_name", _GATE_NAME)
        span.set_attribute("purpose", purpose)
        span.set_attribute("window_start", window_start)
        span.set_attribute("window_end", window_end)
        span.set_attribute("current_rows", len(current_df))

        result = monitor.run_consent_aware_drift_check(
            reference_df,
            current_df,
            user_id_col=user_id_col,
            window_start=window_start,
            window_end=window_end,
            column_mapping=column_mapping,
            run_evidently=run_evidently,
        )

        action_taken = "alerted" if result.has_revoked_samples else "passed"
        consent_status = "revoked" if result.has_revoked_samples else "granted"

        # Build a compact user_id string for the span (up to 5 IDs)
        revoked_ids = [a.user_id for a in result.alerts[:5]]
        user_id_label = ";".join(revoked_ids) if revoked_ids else "none"

        span.set_attribute("user_id", user_id_label)
        span.set_attribute("consent_status", consent_status)
        span.set_attribute("action_taken", action_taken)
        span.set_attribute("has_revoked_samples", str(result.has_revoked_samples))
        span.set_attribute("alerts_fired", len(result.alerts))
        span.set_attribute("revoked_count", result.revoked_count)

        # Capture OTel trace ID
        trace_id_hex: str | None = None
        try:
            from opentelemetry import trace as otel_trace  # noqa: PLC0415
            ctx = span.get_span_context()
            if ctx and ctx.trace_id:
                trace_id_hex = format(ctx.trace_id, "032x")
        except Exception:  # noqa: BLE001
            pass

    # ── Audit log insert (async-aware) ────────────────────────────────────────
    if db_pool is not None:
        import asyncio  # noqa: PLC0415
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                _write_audit_row(
                    db_pool,
                    user_id=user_id_label,
                    action_taken=action_taken,
                    consent_status=consent_status,
                    purpose=purpose,
                    metadata={
                        "alerts_fired": len(result.alerts),
                        "revoked_count": result.revoked_count,
                        "window_start": window_start,
                        "window_end": window_end,
                    },
                    trace_id=trace_id_hex,
                )
            )
        except RuntimeError:
            # Called from sync context — run in a new event loop
            asyncio.run(
                _write_audit_row(
                    db_pool,
                    user_id=user_id_label,
                    action_taken=action_taken,
                    consent_status=consent_status,
                    purpose=purpose,
                    metadata={
                        "alerts_fired": len(result.alerts),
                        "revoked_count": result.revoked_count,
                    },
                    trace_id=trace_id_hex,
                )
            )

    return result


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
        logger.error("audit_log insert failed (monitoring_gate): %s", exc)
