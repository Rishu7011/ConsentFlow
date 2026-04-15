"""
tests/test_monitoring_gate.py — Unit tests for Step 6 (Drift Monitor Integration).

Five tests matching the implementation plan
-------------------------------------------
Test 1 (Scenario 1):  All samples have granted consent →
                       alerts == [], has_revoked_samples False, revoked_count == 0
Test 2 (Scenario 2):  Some samples have revoked consent →
                       len(alerts) > 0, has_revoked_samples True, correct revoked_count
Test 3 (Scenario 3):  DriftAlert fields fully validated —
                       user_id, severity, window_start/end, timestamp, to_dict()
Edge case 1:          Missing user_id column → raises ValueError with "user_id" in message
Edge case 2:          Empty current DataFrame → zero alerts, no crash, revoked_count == 0

Design
------
* No real Redis, Postgres, Kafka, or Evidently server required.
* ``consent_fn`` injected as a plain dict lookup — same pattern as
  ``search_runs_fn`` / ``quarantine_fn`` in test_step5.py.
* ``run_evidently=False`` passed to every orchestration call — Evidently's
  Report is skipped so tests are fast and dependency-free.
* Pure sync tests — Evidently is a sync library; pytest-asyncio is not needed.
* Boolean assertions use ``assert result.has_revoked_samples`` (coercion) rather
  than ``assert result.has_revoked_samples is True`` to avoid np.bool_ failures.
"""
from __future__ import annotations

import logging
from uuid import uuid4

import pandas as pd
import pytest

from consentflow.monitoring_gate import (
    ConsentAwareDriftMonitor,
    DriftAlert,
    DriftCheckResult,
)

logger = logging.getLogger(__name__)

# ── Synthetic user IDs ────────────────────────────────────────────────────────

USER_GRANTED_1 = str(uuid4())
USER_GRANTED_2 = str(uuid4())
USER_REVOKED_1 = str(uuid4())
USER_REVOKED_2 = str(uuid4())

# ── Injected consent map (no Redis / Postgres needed) ─────────────────────────

_CONSENT_MAP: dict[str, bool] = {
    USER_GRANTED_1: True,
    USER_GRANTED_2: True,
    USER_REVOKED_1: False,
    USER_REVOKED_2: False,
}


def _fake_consent_fn(user_id: str, purpose: str) -> bool:  # noqa: ARG001
    """Simulate is_user_consented_sync() from a dict — no network calls."""
    return _CONSENT_MAP.get(user_id, True)  # unknown user → granted by default


# ── Shared helpers ────────────────────────────────────────────────────────────


def _make_monitor(severity_threshold: int = 5) -> ConsentAwareDriftMonitor:
    """Return a monitor with the fake consent function already injected."""
    return ConsentAwareDriftMonitor(
        consent_fn=_fake_consent_fn,
        purpose="monitoring",
        severity_threshold=severity_threshold,
    )


def _make_reference_df() -> pd.DataFrame:
    """Minimal baseline DataFrame (only needed when run_evidently=True)."""
    return pd.DataFrame(
        {
            "feature_a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "feature_b": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )


# ── Test 1: All granted → no alerts ──────────────────────────────────────────


def test_all_granted_no_alerts():
    """
    SCENARIO 1
    ----------
    Current window contains only samples from users with granted consent.

    Expected
    --------
    * ``alerts == []``
    * ``has_revoked_samples`` is falsy
    * ``revoked_count == 0``
    * Every ``_consent_status`` value in the tagged DataFrame is ``"granted"``
    """
    current_df = pd.DataFrame(
        {
            "user_id": [
                USER_GRANTED_1,
                USER_GRANTED_1,
                USER_GRANTED_2,
                USER_GRANTED_2,
                USER_GRANTED_1,
            ],
            "feature_a": [1.1, 2.2, 3.3, 4.4, 5.5],
            "feature_b": [11.0, 22.0, 33.0, 44.0, 55.0],
        }
    )

    monitor = _make_monitor()
    result = monitor.run_consent_aware_drift_check(
        _make_reference_df(),
        current_df,
        window_start="2026-04-08T00:00:00Z",
        window_end="2026-04-08T01:00:00Z",
        run_evidently=False,
    )

    assert isinstance(result, DriftCheckResult)
    assert result.alerts == [], f"Expected no alerts, got: {result.alerts}"
    assert not result.has_revoked_samples, "has_revoked_samples must be falsy when all consent granted"
    assert result.revoked_count == 0, f"Expected revoked_count=0, got {result.revoked_count}"
    assert "_consent_status" in result.tagged_df.columns
    assert (result.tagged_df["_consent_status"] == "granted").all(), (
        "Every row must be tagged 'granted'"
    )

    logger.info("Test 1 PASS — all granted, zero alerts generated")


# ── Test 2: Some revoked → alerts fired ──────────────────────────────────────


def test_revoked_samples_trigger_alerts():
    """
    SCENARIO 2
    ----------
    Current window has 3 rows from USER_REVOKED_1 and 2 from USER_GRANTED_1.

    Expected
    --------
    * ``has_revoked_samples`` is truthy
    * exactly 1 alert (one unique revoked user)
    * ``revoked_count == 3``
    * the alert's ``user_id`` matches USER_REVOKED_1
    """
    current_df = pd.DataFrame(
        {
            "user_id": [
                USER_REVOKED_1,  # revoked  ─┐
                USER_REVOKED_1,  # revoked   ├─ 3 rows
                USER_REVOKED_1,  # revoked  ─┘
                USER_GRANTED_1,  # granted  ─┐
                USER_GRANTED_1,  # granted  ─┘ 2 rows
            ],
            "feature_a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "feature_b": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )

    monitor = _make_monitor()
    result = monitor.run_consent_aware_drift_check(
        _make_reference_df(),
        current_df,
        window_start="2026-04-08T00:00:00Z",
        window_end="2026-04-08T01:00:00Z",
        run_evidently=False,
    )

    assert result.has_revoked_samples, "has_revoked_samples must be truthy"
    assert len(result.alerts) == 1, (
        f"Expected exactly 1 alert (one revoked user), got {len(result.alerts)}"
    )
    assert result.revoked_count == 3, f"Expected revoked_count=3, got {result.revoked_count}"

    alert = result.alerts[0]
    assert alert.user_id == USER_REVOKED_1
    assert alert.revoked_count == 3

    logger.info(
        "Test 2 PASS — 3 revoked rows detected, 1 alert for user_id=%s",
        USER_REVOKED_1,
    )


# ── Test 3: DriftAlert fields fully validated ─────────────────────────────────


def test_drift_alert_fields_are_correct():
    """
    SCENARIO 3
    ----------
    6 rows from USER_REVOKED_1 → severity == ``"critical"`` (>= default threshold 5).

    Validates every DriftAlert field and the to_dict() round-trip.
    """
    WINDOW_START = "2026-04-08T00:00:00Z"
    WINDOW_END = "2026-04-08T01:00:00Z"

    # 6 revoked rows → "critical"; 1 granted row alongside
    current_df = pd.DataFrame(
        {
            "user_id": [USER_REVOKED_1] * 6 + [USER_GRANTED_1],
            "feature_a": [float(i) for i in range(7)],
            "feature_b": [float(i * 10) for i in range(7)],
        }
    )

    monitor = _make_monitor(severity_threshold=5)
    result = monitor.run_consent_aware_drift_check(
        _make_reference_df(),
        current_df,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        run_evidently=False,
    )

    assert len(result.alerts) >= 1, "Expected at least one alert"
    alert = next(a for a in result.alerts if a.user_id == USER_REVOKED_1)

    # ── Field assertions ──────────────────────────────────────────────────────
    assert isinstance(alert, DriftAlert)
    assert alert.user_id == USER_REVOKED_1
    assert alert.revoked_count == 6, f"Expected revoked_count=6, got {alert.revoked_count}"
    assert alert.severity == "critical", (
        f"6 rows >= threshold 5 must be 'critical', got {alert.severity!r}"
    )
    assert alert.window_start == WINDOW_START
    assert alert.window_end == WINDOW_END
    assert alert.timestamp, "timestamp must not be empty"

    # ── to_dict() round-trip ──────────────────────────────────────────────────
    d = alert.to_dict()
    assert d["user_id"] == USER_REVOKED_1
    assert d["revoked_count"] == 6
    assert d["severity"] == "critical"
    assert d["window_start"] == WINDOW_START
    assert d["window_end"] == WINDOW_END
    assert "timestamp" in d

    logger.info("Test 3 PASS — all DriftAlert fields and to_dict() validated")


# ── Edge case 1: Missing user_id column raises ValueError ────────────────────


def test_missing_user_id_column_raises_value_error():
    """
    EDGE CASE 1
    -----------
    A DataFrame that has no 'user_id' column must raise a ``ValueError``
    with "user_id" in the message, not silently pass or raise a ``KeyError``.
    """
    df_no_uid = pd.DataFrame(
        {
            "feature_a": [1.0, 2.0, 3.0],
            "feature_b": [10.0, 20.0, 30.0],
        }
    )
    monitor = _make_monitor()

    with pytest.raises(ValueError, match="user_id"):
        monitor.tag_samples_with_consent(df_no_uid, user_id_col="user_id")

    logger.info("Edge case 1 PASS — ValueError raised for missing user_id column")


# ── Edge case 2: Empty DataFrame → zero alerts, no crash ─────────────────────


def test_empty_dataframe_produces_no_alerts():
    """
    EDGE CASE 2
    -----------
    An empty current DataFrame (0 rows, correct columns present) must return
    zero alerts without raising any exception.

    Expected
    --------
    * ``alerts == []``
    * ``has_revoked_samples`` is falsy
    * ``revoked_count == 0``
    * ``_consent_status`` column still present in tagged_df
    """
    empty_df = pd.DataFrame(columns=["user_id", "feature_a", "feature_b"])

    monitor = _make_monitor()
    result = monitor.run_consent_aware_drift_check(
        _make_reference_df(),
        empty_df,
        window_start="2026-04-08T00:00:00Z",
        window_end="2026-04-08T01:00:00Z",
        run_evidently=False,
    )

    assert result.alerts == [], f"Expected no alerts for empty DataFrame, got {result.alerts}"
    assert not result.has_revoked_samples, "has_revoked_samples must be falsy for empty input"
    assert result.revoked_count == 0
    assert "_consent_status" in result.tagged_df.columns

    logger.info("Edge case 2 PASS — empty DataFrame: zero alerts, no crash")
