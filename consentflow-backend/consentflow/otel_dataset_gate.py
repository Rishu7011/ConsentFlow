"""
consentflow/otel_dataset_gate.py — OTel-instrumented dataset gate wrapper (Step 7).

Wraps :func:`~consentflow.dataset_gate.register_dataset_with_consent_check`
with an OpenTelemetry span and writes one row to the ``audit_log`` table.

Design
------
* ``tracer`` is an injected parameter (default ``None`` → ``get_tracer()``).
  Tests pass a ``NonRecordingTracer`` so no OTLP endpoint is needed.
* ``db_pool`` is forwarded both to the underlying gate function AND used to
  insert the audit row — consistent with the injected-pool pattern in
  Steps 1–6.
* The audit insert is fire-and-forget: an error is logged but never raised,
  so a DB hiccup never breaks the gate's primary behaviour.

Span attributes
---------------
gate_name      : "dataset_gate"
user_id        : run_id (dataset gate operates on batches, not single users)
consent_status : "mixed" when some records were anonymized, "granted" otherwise
action_taken   : "anonymized" | "passed"
total_records  : total record count
anonymized_count: number of anonymized records
"""
from __future__ import annotations

import json
import logging
from typing import Any

from consentflow.dataset_gate import GateResult, register_dataset_with_consent_check
from consentflow.telemetry import get_tracer

logger = logging.getLogger(__name__)

_GATE_NAME = "dataset_gate"


async def traced_register_dataset(
    dataset: list[dict[str, Any]],
    run_id: str,
    *,
    tracer: Any = None,
    db_pool: Any = None,
    redis_client: Any = None,
    purpose: str = "model_training",
    mlflow_experiment: str = "ConsentFlow / Dataset Gate",
) -> GateResult:
    """
    OTel-instrumented wrapper around ``register_dataset_with_consent_check``.

    Parameters
    ----------
    dataset:           List of record dicts, each with a ``user_id`` key.
    run_id:            Pipeline run identifier.
    tracer:            OTel tracer; defaults to the global tracer for this module.
    db_pool:           asyncpg pool — forwarded to the gate and used for audit insert.
    redis_client:      Redis client forwarded to the gate.
    purpose:           Consent purpose string.
    mlflow_experiment: MLflow experiment name.

    Returns
    -------
    :class:`~consentflow.dataset_gate.GateResult`
    """
    _tracer = tracer if tracer is not None else get_tracer(_GATE_NAME)
    action_taken = "passed"
    consent_status = "granted"

    with _tracer.start_as_current_span(f"{_GATE_NAME}.check") as span:
        span.set_attribute("gate_name", _GATE_NAME)
        span.set_attribute("run_id", run_id)
        span.set_attribute("purpose", purpose)

        result = await register_dataset_with_consent_check(
            dataset,
            run_id,
            purpose=purpose,
            redis_client=redis_client,
            db_pool=db_pool,
            mlflow_experiment=mlflow_experiment,
        )

        action_taken = "anonymized" if result.anonymized_count > 0 else "passed"
        consent_status = "revoked" if result.anonymized_count > 0 else "granted"

        span.set_attribute("consent_status", consent_status)
        span.set_attribute("action_taken", action_taken)
        span.set_attribute("total_records", result.total_records)
        span.set_attribute("anonymized_count", result.anonymized_count)

        # Capture OTel trace ID for the audit row (hex string or empty)
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
            user_id=run_id,   # batch gate — use run_id as the identity
            action_taken=action_taken,
            consent_status=consent_status,
            purpose=purpose,
            metadata={
                "total_records": result.total_records,
                "anonymized_count": result.anonymized_count,
                "mlflow_run_id": result.mlflow_run_id,
            },
            trace_id=trace_id_hex,
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
        logger.error("audit_log insert failed (dataset_gate): %s", exc)
