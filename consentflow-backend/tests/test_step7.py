"""
tests/test_step7.py — Unit tests for Step 7 (Observability Dashboard).

Eight tests covering all four OTel gate wrappers and the audit trail endpoint.

Design principles
-----------------
* No real OTel collector — ``NonRecordingTracer`` injected into every wrapper.
* No real Postgres for gate wrappers — ``db_pool=None`` skips audit inserts.
* Audit trail endpoint tested against FakePool from conftest with controlled rows.
* ``InMemorySpanExporter`` used to assert span attributes where verifiable.
* No existing tests modified, no external services required.

Test index
----------
T1  traced_inference_check — blocked path (consented=False)
T2  traced_inference_check — passed path (consented=True)
T3  traced_training_quarantine — span attributes correct
T4  traced_drift_check — alerted path (revoked samples present)
T5  traced_drift_check — passed path (all granted)
T6  traced_register_dataset — action_taken attribute (all consented)
T7  GET /audit/trail — empty table returns {"entries":[],"total":0}
T8  GET /audit/trail — with filter params, correct response shape
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pandas as pd
import pytest

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

logger = logging.getLogger(__name__)

# ── Helper: build an SDK tracer backed by InMemorySpanExporter ────────────────


def _make_recording_tracer(exporter: InMemorySpanExporter) -> Any:
    """Return a real SDK tracer that writes spans to *exporter*."""
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test")


# ── Fake consent function for drift monitor tests ─────────────────────────────

_USER_GRANTED = str(uuid4())
_USER_REVOKED = str(uuid4())

_CONSENT_MAP = {_USER_GRANTED: True, _USER_REVOKED: False}


def _fake_consent_fn(user_id: str, purpose: str) -> bool:  # noqa: ARG001
    return _CONSENT_MAP.get(user_id, True)


def _make_reference_df() -> pd.DataFrame:
    return pd.DataFrame({"feature_a": [1.0, 2.0], "feature_b": [10.0, 20.0]})


# ═══════════════════════════════════════════════════════════════════════════════
# T1 — traced_inference_check: blocked (consented=False)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_traced_inference_check_blocked():
    """
    T1: When consent is revoked, traced_inference_check must return "blocked"
    and the span must carry consent_status="revoked" and action_taken="blocked".
    """
    from consentflow.otel_inference_gate import traced_inference_check

    exporter = InMemorySpanExporter()
    tracer = _make_recording_tracer(exporter)

    result = await traced_inference_check(
        user_id=str(uuid4()),
        consented=False,
        path="/infer/predict",
        tracer=tracer,
        db_pool=None,
    )

    assert result == "blocked", f"Expected 'blocked', got {result!r}"

    spans = exporter.get_finished_spans()
    assert len(spans) == 1, f"Expected 1 span, got {len(spans)}"

    attrs = spans[0].attributes
    assert attrs["gate_name"] == "inference_gate"
    assert attrs["consent_status"] == "revoked"
    assert attrs["action_taken"] == "blocked"

    logger.info("T1 PASS — inference_gate blocked span attributes verified")


# ═══════════════════════════════════════════════════════════════════════════════
# T2 — traced_inference_check: passed (consented=True)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_traced_inference_check_passed():
    """
    T2: When consent is granted, traced_inference_check must return "passed"
    and the span must carry consent_status="granted" and action_taken="passed".
    """
    from consentflow.otel_inference_gate import traced_inference_check

    exporter = InMemorySpanExporter()
    tracer = _make_recording_tracer(exporter)

    result = await traced_inference_check(
        user_id=str(uuid4()),
        consented=True,
        path="/infer/predict",
        tracer=tracer,
        db_pool=None,
    )

    assert result == "passed", f"Expected 'passed', got {result!r}"

    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    attrs = spans[0].attributes
    assert attrs["gate_name"] == "inference_gate"
    assert attrs["consent_status"] == "granted"
    assert attrs["action_taken"] == "passed"

    logger.info("T2 PASS — inference_gate passed span attributes verified")


# ═══════════════════════════════════════════════════════════════════════════════
# T3 — traced_training_quarantine span attributes
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_traced_training_quarantine_span():
    """
    T3: traced_training_quarantine must produce a span with correct attributes:
    gate_name="training_gate", consent_status="revoked", action_taken="quarantined",
    quarantined_run_count matching the input run_ids list length.
    """
    from consentflow.otel_training_gate import traced_training_quarantine

    exporter = InMemorySpanExporter()
    tracer = _make_recording_tracer(exporter)

    run_ids = ["run-aaa-111", "run-bbb-222", "run-ccc-333"]
    user_id = str(uuid4())

    await traced_training_quarantine(
        user_id=user_id,
        run_ids=run_ids,
        tracer=tracer,
        db_pool=None,
    )

    spans = exporter.get_finished_spans()
    assert len(spans) == 1, f"Expected 1 span, got {len(spans)}"

    attrs = spans[0].attributes
    assert attrs["gate_name"] == "training_gate"
    assert attrs["user_id"] == user_id
    assert attrs["consent_status"] == "revoked"
    assert attrs["action_taken"] == "quarantined"
    assert attrs["quarantined_run_count"] == 3

    logger.info("T3 PASS — training_gate quarantine span attributes verified (run_count=3)")


# ═══════════════════════════════════════════════════════════════════════════════
# T4 — traced_drift_check: alerted (revoked samples present)
# ═══════════════════════════════════════════════════════════════════════════════


def test_traced_drift_check_alerted():
    """
    T4: When the monitoring window contains revoked-user samples, traced_drift_check
    must return a DriftCheckResult with has_revoked_samples=True, and the span must
    carry action_taken="alerted" and consent_status="revoked".
    """
    from consentflow.monitoring_gate import ConsentAwareDriftMonitor
    from consentflow.otel_monitoring_gate import traced_drift_check

    exporter = InMemorySpanExporter()
    tracer = _make_recording_tracer(exporter)

    monitor = ConsentAwareDriftMonitor(
        consent_fn=_fake_consent_fn,
        purpose="monitoring",
    )

    current_df = pd.DataFrame({
        "user_id": [_USER_REVOKED, _USER_REVOKED, _USER_GRANTED],
        "feature_a": [1.0, 2.0, 3.0],
        "feature_b": [10.0, 20.0, 30.0],
    })

    result = traced_drift_check(
        monitor,
        _make_reference_df(),
        current_df,
        run_evidently=False,
        tracer=tracer,
        db_pool=None,
    )

    assert result.has_revoked_samples, "Expected has_revoked_samples=True"
    assert len(result.alerts) == 1

    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    attrs = spans[0].attributes
    assert attrs["gate_name"] == "monitoring_gate"
    assert attrs["consent_status"] == "revoked"
    assert attrs["action_taken"] == "alerted"
    assert attrs["alerts_fired"] == 1
    assert attrs["revoked_count"] == 2

    logger.info("T4 PASS — monitoring_gate alerted span attributes verified")


# ═══════════════════════════════════════════════════════════════════════════════
# T5 — traced_drift_check: passed (all granted)
# ═══════════════════════════════════════════════════════════════════════════════


def test_traced_drift_check_passed():
    """
    T5: When all samples are granted, traced_drift_check must return
    has_revoked_samples=False and the span must carry action_taken="passed".
    """
    from consentflow.monitoring_gate import ConsentAwareDriftMonitor
    from consentflow.otel_monitoring_gate import traced_drift_check

    exporter = InMemorySpanExporter()
    tracer = _make_recording_tracer(exporter)

    monitor = ConsentAwareDriftMonitor(
        consent_fn=_fake_consent_fn,
        purpose="monitoring",
    )

    current_df = pd.DataFrame({
        "user_id": [_USER_GRANTED, _USER_GRANTED],
        "feature_a": [1.0, 2.0],
        "feature_b": [10.0, 20.0],
    })

    result = traced_drift_check(
        monitor,
        _make_reference_df(),
        current_df,
        run_evidently=False,
        tracer=tracer,
        db_pool=None,
    )

    assert not result.has_revoked_samples, "Expected has_revoked_samples=False"
    assert result.alerts == []

    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    attrs = spans[0].attributes
    assert attrs["gate_name"] == "monitoring_gate"
    assert attrs["consent_status"] == "granted"
    assert attrs["action_taken"] == "passed"
    assert attrs["alerts_fired"] == 0

    logger.info("T5 PASS — monitoring_gate passed span attributes verified")


# ═══════════════════════════════════════════════════════════════════════════════
# T6 — traced_register_dataset: span attributes (all consented)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_traced_register_dataset_all_consented():
    """
    T6: When all dataset records are consented, traced_register_dataset must
    produce action_taken="passed" on the span and anonymized_count=0.

    Uses a fake is_user_consented that always returns True, bypassing Redis/Postgres.
    """
    from unittest.mock import patch, AsyncMock

    from consentflow.otel_dataset_gate import traced_register_dataset

    exporter = InMemorySpanExporter()
    tracer = _make_recording_tracer(exporter)

    user_id = str(uuid4())
    dataset = [{"user_id": user_id, "text": "hello world"}]

    # Patch is_user_consented inside dataset_gate to always return True
    with patch(
        "consentflow.dataset_gate.is_user_consented",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await traced_register_dataset(
            dataset=dataset,
            run_id="test-run-001",
            tracer=tracer,
            db_pool=None,
            redis_client=None,
        )

    assert result.anonymized_count == 0
    assert result.consented_count == 1

    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    attrs = spans[0].attributes
    assert attrs["gate_name"] == "dataset_gate"
    assert attrs["action_taken"] == "passed"
    assert attrs["consent_status"] == "granted"
    assert attrs["total_records"] == 1
    assert attrs["anonymized_count"] == 0

    logger.info("T6 PASS — dataset_gate passed span attributes verified")


# ═══════════════════════════════════════════════════════════════════════════════
# T7 — GET /audit/trail: empty table returns correct shape
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_audit_trail_endpoint_empty(client):
    """
    T7: GET /audit/trail against an empty FakePool must return:
      {"entries": [], "total": 0}
    without any error.

    FakePool.fetchval returns 1 by default; override it to 0 for the count.
    FakePool.fetch returns [] by default — perfect for empty table.
    """
    # fetchval (COUNT) returns 0, fetch (rows) returns []
    client.fake_pool.rows = []

    # Patch fetchval to return 0 (empty table count)
    original_fetchval = None

    class _ZeroCountConnection:
        async def fetchval(self, *args, **kwargs):
            return 0

        async def fetch(self, *args, **kwargs):
            return []

        async def execute(self, *args, **kwargs):
            return None

    class _ZeroPool:
        def acquire(self):
            return self

        async def __aenter__(self):
            return _ZeroCountConnection()

        async def __aexit__(self, *args):
            pass

    from consentflow.app.main import app
    app.state.db_pool = _ZeroPool()

    response = await client.get("/audit/trail")

    # Restore original fake pool
    app.state.db_pool = client.fake_pool

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["entries"] == [], f"Expected empty entries, got {data['entries']}"
    assert data["total"] == 0, f"Expected total=0, got {data['total']}"

    logger.info("T7 PASS — /audit/trail returns empty response correctly")


# ═══════════════════════════════════════════════════════════════════════════════
# T8 — GET /audit/trail: returns correct shaped entries
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_audit_trail_endpoint_with_entries(client):
    """
    T8: GET /audit/trail with a FakePool that returns one synthetic audit row
    must return a correctly shaped AuditTrailResponse with total=1 and one entry
    containing all expected fields.
    """
    import uuid as uuid_mod
    from datetime import datetime, timezone

    fake_id = uuid_mod.uuid4()
    fake_user = str(uuid_mod.uuid4())
    fake_time = datetime.now(timezone.utc)

    # Build a fake asyncpg record-like dict
    class _FakeRecord(dict):
        """dict subclass that also supports attribute access like asyncpg Record."""
        def __getattr__(self, item):
            return self[item]

    fake_row = _FakeRecord({
        "id": fake_id,
        "event_time": fake_time,
        "user_id": fake_user,
        "gate_name": "inference_gate",
        "action_taken": "blocked",
        "consent_status": "revoked",
        "purpose": "inference",
        "metadata": json.dumps({"path": "/infer/predict"}),
        "trace_id": "abc123",
    })

    class _OneRowConnection:
        async def fetchval(self, *args, **kwargs):
            return 1

        async def fetch(self, *args, **kwargs):
            return [fake_row]

        async def execute(self, *args, **kwargs):
            return None

    class _OneRowPool:
        def acquire(self):
            return self

        async def __aenter__(self):
            return _OneRowConnection()

        async def __aexit__(self, *args):
            pass

    from consentflow.app.main import app
    app.state.db_pool = _OneRowPool()

    response = await client.get("/audit/trail")

    # Restore pool
    app.state.db_pool = client.fake_pool

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert data["total"] == 1
    assert len(data["entries"]) == 1

    entry = data["entries"][0]
    assert entry["gate_name"] == "inference_gate"
    assert entry["action_taken"] == "blocked"
    assert entry["consent_status"] == "revoked"
    assert entry["user_id"] == fake_user
    assert entry["purpose"] == "inference"
    assert entry["trace_id"] == "abc123"
    # metadata was JSON-string in fake DB row — router must parse it to dict
    assert isinstance(entry["metadata"], dict)
    assert entry["metadata"]["path"] == "/infer/predict"

    logger.info(
        "T8 PASS — /audit/trail returns correctly shaped AuditLogEntry with metadata parsed"
    )
