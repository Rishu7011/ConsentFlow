"""
consentflow/monitoring_gate.py — Consent-aware Evidently drift monitor (Step 6).

Purpose
-------
Wraps Evidently AI's ``DataDriftPreset`` so every sample in a monitoring window
is tagged with its current consent status.  If any revoked-user sample is found
in the window a :class:`DriftAlert` is fired — demonstrating that consent
enforcement extends to post-deployment monitoring.

Design
------
* :class:`ConsentAwareDriftMonitor` accepts an optional ``consent_fn`` parameter
  (signature: ``(user_id: str, purpose: str) -> bool``) that defaults to
  :func:`~consentflow.sdk.is_user_consented_sync` in production.  Inject a
  plain dict-lookup in unit tests — no Redis/Postgres required.

* Evidently imports are **lazy** (inside ``run_drift_report``), so the module can
  be imported and unit-tested without Evidently installed as long as
  ``run_evidently=False`` is passed to :meth:`run_consent_aware_drift_check`.

* :class:`DriftAlert` and :class:`DriftCheckResult` are plain dataclasses,
  consistent with :class:`~consentflow.training_gate.QuarantineRecord` and
  :class:`~consentflow.dataset_gate.GateResult`.

* Severity logic:
  - ``"warning"``  — 1 to (threshold - 1) revoked rows for a user.
  - ``"critical"`` — threshold or more revoked rows (default threshold: 5).

Running standalone
------------------
    python -m consentflow.monitoring_gate

Injected dependencies (for testing)
------------------------------------
``ConsentAwareDriftMonitor.__init__`` accepts:

* ``consent_fn``         — replaces ``sdk.is_user_consented_sync``.
* ``severity_threshold`` — row count at / above which severity is ``"critical"``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

logger = logging.getLogger(__name__)


# ── DriftAlert ────────────────────────────────────────────────────────────────


@dataclass
class DriftAlert:
    """
    Structured alert emitted when a revoked-user sample appears in a drift window.

    Attributes
    ----------
    user_id:       UUID of the revoked user found in the window.
    window_start:  ISO-8601 start of the monitoring window.
    window_end:    ISO-8601 end of the monitoring window.
    revoked_count: Number of rows belonging to this revoked user in the window.
    severity:      ``"warning"`` (<threshold rows) or ``"critical"`` (>=threshold).
    timestamp:     ISO-8601 UTC time when the alert was created.
    """

    user_id: str
    window_start: str
    window_end: str
    revoked_count: int
    severity: str  # "warning" | "critical"
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict representation suitable for JSON serialisation."""
        return {
            "user_id": self.user_id,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "revoked_count": self.revoked_count,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }


# ── DriftCheckResult ──────────────────────────────────────────────────────────


@dataclass
class DriftCheckResult:
    """
    Full result of a consent-aware drift check.

    Attributes
    ----------
    tagged_df:           Current DataFrame with ``_consent_status`` column added.
    report:              Raw Evidently Report object (``None`` when skipped).
    alerts:              List of :class:`DriftAlert` objects; empty if no revoked rows.
    has_revoked_samples: ``True`` iff at least one revoked-user row is in the window.
    revoked_count:       Total number of revoked-user rows across all alerts.
    """

    tagged_df: pd.DataFrame
    report: Any  # evidently.report.Report | None
    alerts: list[DriftAlert] = field(default_factory=list)
    has_revoked_samples: bool = False
    revoked_count: int = 0


# ── ConsentAwareDriftMonitor ──────────────────────────────────────────────────


class ConsentAwareDriftMonitor:
    """
    Wraps Evidently's DataDriftPreset with per-sample consent-status tagging.

    Parameters
    ----------
    consent_fn:          Callable ``(user_id: str, purpose: str) -> bool``.
                         Returns ``True`` iff the user has active consent for
                         *purpose*.  Defaults to
                         :func:`~consentflow.sdk.is_user_consented_sync`.
                         Inject a lightweight fake in unit tests.
    purpose:             Consent purpose string used for all lookups
                         (default: ``"monitoring"``).
    severity_threshold:  Row count at / above which severity becomes
                         ``"critical"`` (default: ``5``).
    """

    def __init__(
        self,
        *,
        consent_fn: Callable[[str, str], bool] | None = None,
        purpose: str = "monitoring",
        severity_threshold: int = 5,
    ) -> None:
        self._purpose = purpose
        self._severity_threshold = severity_threshold

        if consent_fn is not None:
            self._consent_fn = consent_fn
        else:
            # Lazy import so tests injecting consent_fn don't need live services
            from consentflow.sdk import is_user_consented_sync  # noqa: PLC0415

            self._consent_fn = is_user_consented_sync

    # ── Consent tagging ───────────────────────────────────────────────────────

    def tag_samples_with_consent(
        self,
        df: pd.DataFrame,
        user_id_col: str = "user_id",
    ) -> pd.DataFrame:
        """
        Add a ``_consent_status`` column (``"granted"`` / ``"revoked"``) to *df*.

        Parameters
        ----------
        df:          DataFrame to tag.  **Must** contain *user_id_col*.
        user_id_col: Column name holding the user UUID (default: ``"user_id"``).

        Returns
        -------
        A copy of *df* with the ``_consent_status`` column appended.

        Raises
        ------
        ValueError  If *user_id_col* is not present in *df*.
        """
        if user_id_col not in df.columns:
            raise ValueError(
                f"tag_samples_with_consent: column {user_id_col!r} not found in "
                f"DataFrame.  Available columns: {list(df.columns)}"
            )

        tagged = df.copy()

        def _get_status(user_id: Any) -> str:
            try:
                consented = self._consent_fn(str(user_id), self._purpose)
                return "granted" if consented else "revoked"
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "monitoring_gate: consent lookup error user_id=%s error=%s — treating as revoked",
                    user_id,
                    exc,
                )
                return "revoked"  # fail-closed

        tagged["_consent_status"] = tagged[user_id_col].map(_get_status)

        granted = (tagged["_consent_status"] == "granted").sum()
        revoked = (tagged["_consent_status"] == "revoked").sum()
        logger.info(
            "tag_samples_with_consent: tagged %d rows — granted=%d  revoked=%d  purpose=%s",
            len(tagged),
            granted,
            revoked,
            self._purpose,
        )
        return tagged

    # ── Evidently drift report ────────────────────────────────────────────────

    def run_drift_report(
        self,
        reference_df: pd.DataFrame,
        current_df: pd.DataFrame,
        column_mapping: Any | None = None,
    ) -> Any:
        """
        Run an Evidently ``DataDriftPreset`` report on *current_df* vs *reference_df*.

        The ``_consent_status`` column is stripped before Evidently sees the data
        (it is a ConsentFlow-internal column, not a model feature).

        Parameters
        ----------
        reference_df:   Baseline / reference dataset (training distribution).
        current_df:     Current production monitoring window.
        column_mapping: Optional Evidently ``ColumnMapping`` for custom roles.

        Returns
        -------
        Executed Evidently ``Report`` object.
        """
        # Lazy imports — Evidently is only needed when this method is called
        from evidently.metric_preset import DataDriftPreset  # type: ignore[import-untyped]
        from evidently.report import Report  # type: ignore[import-untyped]

        # Strip internal ConsentFlow columns before computing drift
        _internal = ["_consent_status"]
        ref = reference_df.drop(columns=[c for c in _internal if c in reference_df.columns])
        cur = current_df.drop(columns=[c for c in _internal if c in current_df.columns])

        report = Report(metrics=[DataDriftPreset()])
        report.run(reference_data=ref, current_data=cur, column_mapping=column_mapping)

        logger.info(
            "run_drift_report: Evidently DataDriftPreset complete — "
            "reference=%d rows  current=%d rows",
            len(ref),
            len(cur),
        )
        return report

    # ── Revocation alert scanning ─────────────────────────────────────────────

    def check_for_revoked_samples(
        self,
        tagged_df: pd.DataFrame,
        window_start: str = "",
        window_end: str = "",
    ) -> list[DriftAlert]:
        """
        Inspect ``_consent_status`` and emit one :class:`DriftAlert` per unique
        revoked user found in the monitoring window.

        Parameters
        ----------
        tagged_df:    DataFrame produced by :meth:`tag_samples_with_consent`.
        window_start: ISO-8601 start timestamp stored in each alert.
        window_end:   ISO-8601 end timestamp stored in each alert.

        Returns
        -------
        List of :class:`DriftAlert` — one per unique revoked user.
        Empty list when no revoked samples are present.
        """
        if "_consent_status" not in tagged_df.columns:
            logger.warning(
                "check_for_revoked_samples: '_consent_status' column not found — "
                "call tag_samples_with_consent() first"
            )
            return []

        revoked_rows = tagged_df[tagged_df["_consent_status"] == "revoked"]

        if revoked_rows.empty:
            logger.info("check_for_revoked_samples: no revoked samples in this window")
            return []

        ts = datetime.now(timezone.utc).isoformat()
        alerts: list[DriftAlert] = []

        if "user_id" in tagged_df.columns:
            for uid, group in revoked_rows.groupby("user_id"):
                count = int(len(group))
                severity = "critical" if count >= self._severity_threshold else "warning"
                alert = DriftAlert(
                    user_id=str(uid),
                    window_start=window_start,
                    window_end=window_end,
                    revoked_count=count,
                    severity=severity,
                    timestamp=ts,
                )
                alerts.append(alert)
                logger.warning(
                    "DRIFT ALERT — revoked user in monitoring window: "
                    "user_id=%s  rows=%d  severity=%s",
                    uid,
                    count,
                    severity,
                )
        else:
            # No user_id column — emit a single aggregate alert
            count = int(len(revoked_rows))
            severity = "critical" if count >= self._severity_threshold else "warning"
            alerts.append(
                DriftAlert(
                    user_id="UNKNOWN",
                    window_start=window_start,
                    window_end=window_end,
                    revoked_count=count,
                    severity=severity,
                    timestamp=ts,
                )
            )
            logger.warning(
                "DRIFT ALERT — %d revoked rows in window (user_id column absent)",
                count,
            )

        return alerts

    # ── Orchestration ─────────────────────────────────────────────────────────

    def run_consent_aware_drift_check(
        self,
        reference_df: pd.DataFrame,
        current_df: pd.DataFrame,
        *,
        user_id_col: str = "user_id",
        window_start: str = "",
        window_end: str = "",
        column_mapping: Any | None = None,
        run_evidently: bool = True,
    ) -> DriftCheckResult:
        """
        Orchestrate: tag samples → (optionally) run drift report → scan for revoked.

        Parameters
        ----------
        reference_df:   Baseline dataset (training distribution).
        current_df:     Current production monitoring window to evaluate.
        user_id_col:    Column name holding user UUIDs (default: ``"user_id"``).
        window_start:   ISO-8601 window start — stored in alert metadata.
        window_end:     ISO-8601 window end — stored in alert metadata.
        column_mapping: Optional Evidently ``ColumnMapping``.
        run_evidently:  If ``False``, the Evidently report step is skipped.
                        Use ``False`` in unit tests to avoid the Evidently
                        dependency and speed up the test suite.

        Returns
        -------
        :class:`DriftCheckResult`
        """
        logger.info(
            "ConsentAwareDriftMonitor: starting consent-aware drift check — "
            "current_rows=%d  purpose=%s  run_evidently=%s",
            len(current_df),
            self._purpose,
            run_evidently,
        )

        # ── 1. Tag consent status ─────────────────────────────────────────────
        tagged = self.tag_samples_with_consent(current_df, user_id_col=user_id_col)

        # ── 2. Evidently drift report (optional in tests) ─────────────────────
        report: Any = None
        if run_evidently:
            report = self.run_drift_report(reference_df, tagged, column_mapping=column_mapping)

        # ── 3. Revocation alert scan ──────────────────────────────────────────
        alerts = self.check_for_revoked_samples(
            tagged, window_start=window_start, window_end=window_end
        )

        revoked_count = sum(a.revoked_count for a in alerts)
        has_revoked = revoked_count > 0

        result = DriftCheckResult(
            tagged_df=tagged,
            report=report,
            alerts=alerts,
            has_revoked_samples=has_revoked,
            revoked_count=revoked_count,
        )

        logger.info(
            "ConsentAwareDriftMonitor: check complete — "
            "revoked_rows=%d  alerts_fired=%d  has_revoked=%s",
            revoked_count,
            len(alerts),
            has_revoked,
        )
        return result
