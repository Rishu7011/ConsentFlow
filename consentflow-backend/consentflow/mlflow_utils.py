"""
consentflow/mlflow_utils.py — MLflow helper utilities for the Training Gate.

Public API
----------
search_runs_by_user(user_id, experiment_ids=None)        -> list[mlflow.entities.Run]
apply_quarantine_tags(run_id, user_id, reason=None)      -> None
apply_quarantine_to_registered_model(name, version, ...) -> None
list_quarantined_runs(experiment_ids=None)               -> list[mlflow.entities.Run]

Design Notes
------------
* "Quarantine" is implemented as MLflow tags on both experiment *runs* and on
  registered-model versions.  No models are deleted or retrained — tagging is
  sufficient to surface them for human review and downstream filtering.

* ``consent_status=quarantined`` is the canonical tag used by all other
  ConsentFlow modules to identify flagged runs / model versions.

* Functions are intentionally synchronous: the MLflow tracking client has no
  native async API.  The async ``training_gate.py`` consumer runs them inside
  ``asyncio.to_thread()`` to avoid blocking the event loop.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

import mlflow
from mlflow.entities import Run
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)

# ── Tag keys ──────────────────────────────────────────────────────────────────

CONSENT_STATUS_TAG = "consent_status"
REVOKED_USER_TAG = "revoked_user"
QUARANTINE_REASON_TAG = "quarantine_reason"
QUARANTINE_TIMESTAMP_TAG = "quarantine_timestamp"
STEP_TAG = "step"

QUARANTINED_VALUE = "quarantined"
TRAINING_GATE_STEP = "training_gate"


# ── Internal helpers ──────────────────────────────────────────────────────────


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _make_client() -> MlflowClient:
    """Return a new ``MlflowClient`` bound to the active tracking URI."""
    return MlflowClient()


# ── Run-level helpers ─────────────────────────────────────────────────────────


def search_runs_by_user(
    user_id: str,
    experiment_ids: list[str] | None = None,
) -> list[Run]:
    """
    Search MLflow runs whose tags record ``user_id`` as a training participant.

    ConsentFlow's dataset gate tags every run with ``pipeline_run_id`` and
    ``step=dataset_gate``.  However, individual user-level membership is stored
    as a tag ``revoked_user=<user_id>`` only *after* a prior quarantine pass, so
    the primary search strategy is:

    1. Search all runs (in the given experiments, or ALL experiments if omitted).
    2. Filter by the presence of ``user_id`` in either:
       - ``tags.revoked_user``  (already-quarantined run, re-check)
       - ``tags.trained_users`` (comma-separated list written by dataset gate,
         if present)
       - An artifact ``dataset_gate/<run_id>_cleaned_dataset.json`` that
         contains the user_id — *not* fetched here for performance; callers
         wanting deep artifact scanning should extend this function.

    In practice the training gate relies on the Kafka event already carrying
    the ``user_id``; this function is the fallback "which runs included this
    user?" discovery tool.

    Parameters
    ----------
    user_id:        UUID string of the user whose data may appear in runs.
    experiment_ids: List of MLflow experiment IDs to scope the search.
                    Defaults to ALL experiments when ``None``.

    Returns
    -------
    List of :class:`mlflow.entities.Run` objects that reference *user_id*.
    """
    client = _make_client()

    # Resolve experiment list
    if experiment_ids is None:
        experiments = client.search_experiments()
        experiment_ids = [e.experiment_id for e in experiments]

    if not experiment_ids:
        logger.debug("search_runs_by_user: no experiments found — returning empty")
        return []

    matched: list[Run] = []

    for exp_id in experiment_ids:
        try:
            # Search for runs already tagged with this user (re-quarantine or prior flag)
            runs_tagged = client.search_runs(
                experiment_ids=[exp_id],
                filter_string=f"tags.revoked_user = '{user_id}'",
                max_results=500,
            )
            matched.extend(runs_tagged)

            # Also search for runs whose pipeline_run_id tag matches (broad catch)
            # and cross-check dataset_gate step runs for this experiment
            runs_gate = client.search_runs(
                experiment_ids=[exp_id],
                filter_string=f"tags.step = 'dataset_gate'",
                max_results=500,
            )
            for run in runs_gate:
                # Avoid duplicates with runs already found by tag
                if any(r.info.run_id == run.info.run_id for r in matched):
                    continue
                # Check trained_users tag (comma-separated list)
                trained_users_tag = run.data.tags.get("trained_users", "")
                if user_id in [u.strip() for u in trained_users_tag.split(",") if u.strip()]:
                    matched.append(run)

        except MlflowException as exc:
            logger.warning(
                "search_runs_by_user: MLflow error for experiment_id=%s  error=%s",
                exp_id,
                exc,
            )

    logger.info(
        "search_runs_by_user: found %d run(s) referencing user_id=%s",
        len(matched),
        user_id,
    )
    return matched


def apply_quarantine_tags(
    run_id: str,
    user_id: str,
    *,
    reason: str = "consent_revoked",
    timestamp: str | None = None,
) -> None:
    """
    Apply quarantine tags to an MLflow *run*.

    Tags applied
    ------------
    * ``consent_status``       → ``"quarantined"``
    * ``revoked_user``         → *user_id*
    * ``quarantine_reason``    → *reason*
    * ``quarantine_timestamp`` → ISO-8601 UTC string
    * ``step``                 → ``"training_gate"``

    Parameters
    ----------
    run_id:    MLflow run ID to tag.
    user_id:   UUID string of the user whose consent was revoked.
    reason:    Human-readable quarantine reason (default: ``"consent_revoked"``).
    timestamp: ISO-8601 UTC timestamp; current time is used when omitted.

    Raises
    ------
    MlflowException  If the MLflow tracking server is unreachable.
    """
    ts = timestamp or _utc_now_iso()
    client = _make_client()

    tags: dict[str, str] = {
        CONSENT_STATUS_TAG: QUARANTINED_VALUE,
        REVOKED_USER_TAG: user_id,
        QUARANTINE_REASON_TAG: reason,
        QUARANTINE_TIMESTAMP_TAG: ts,
        STEP_TAG: TRAINING_GATE_STEP,
    }

    for key, value in tags.items():
        client.set_tag(run_id, key, value)

    logger.info(
        "quarantine tags applied — run_id=%s  user_id=%s  reason=%s  ts=%s",
        run_id,
        user_id,
        reason,
        ts,
    )


def apply_quarantine_to_registered_model(
    model_name: str,
    model_version: str | int,
    user_id: str,
    *,
    reason: str = "consent_revoked",
    timestamp: str | None = None,
) -> None:
    """
    Apply quarantine tags to a *registered model version*.

    Parameters
    ----------
    model_name:    Registered model name in the MLflow Model Registry.
    model_version: Version number (int or str).
    user_id:       UUID string of the revoked user.
    reason:        Quarantine reason label.
    timestamp:     ISO-8601 timestamp; defaults to current UTC time.

    Raises
    ------
    MlflowException  If the model or version does not exist.
    """
    ts = timestamp or _utc_now_iso()
    client = _make_client()
    version_str = str(model_version)

    tags: dict[str, str] = {
        CONSENT_STATUS_TAG: QUARANTINED_VALUE,
        REVOKED_USER_TAG: user_id,
        QUARANTINE_REASON_TAG: reason,
        QUARANTINE_TIMESTAMP_TAG: ts,
    }

    for key, value in tags.items():
        client.set_model_version_tag(model_name, version_str, key, value)

    logger.info(
        "quarantine tags applied to registered model — name=%s  version=%s  user_id=%s",
        model_name,
        version_str,
        user_id,
    )


# ── Listing helpers ───────────────────────────────────────────────────────────


def list_quarantined_runs(
    experiment_ids: list[str] | None = None,
) -> list[Run]:
    """
    Return all MLflow runs that have been flagged as quarantined.

    Parameters
    ----------
    experiment_ids: Scope the search to these experiment IDs.
                    Defaults to ALL experiments when ``None``.

    Returns
    -------
    List of :class:`mlflow.entities.Run` with ``consent_status=quarantined``.
    """
    client = _make_client()

    if experiment_ids is None:
        experiments = client.search_experiments()
        experiment_ids = [e.experiment_id for e in experiments]

    if not experiment_ids:
        return []

    quarantined: list[Run] = []
    for exp_id in experiment_ids:
        try:
            runs = client.search_runs(
                experiment_ids=[exp_id],
                filter_string=f"tags.{CONSENT_STATUS_TAG} = '{QUARANTINED_VALUE}'",
                max_results=1000,
            )
            quarantined.extend(runs)
        except MlflowException as exc:
            logger.warning(
                "list_quarantined_runs: error for experiment_id=%s  error=%s",
                exp_id,
                exc,
            )

    logger.debug("list_quarantined_runs: found %d quarantined run(s)", len(quarantined))
    return quarantined
