"""
consentflow/dataset_gate.py — Consent-aware dataset registration gate.

Public API
----------
register_dataset_with_consent_check(
    dataset: list[dict],
    run_id: str,
    *,
    purpose: str = "model_training",
    redis_client=None,
    db_pool=None,
) -> GateResult

Behaviour
---------
For every record in *dataset*:
  1. Calls ``is_user_consented(record["user_id"], purpose)``
  2. If consent is **revoked**  → anonymizes the record with Presidio
  3. If consent is **granted**  → passes through untouched

After processing the full dataset:
  - Logs the cleaned dataset as a JSON artifact to MLflow
  - Logs MLflow metrics: total_records, consented_count, anonymized_count

The function works with or without live Redis / Postgres connections:
test code may inject lightweight fakes via ``redis_client`` and ``db_pool``.
"""
from __future__ import annotations

import json
import logging
import pathlib
import tempfile
from dataclasses import dataclass, field
from typing import Any

import mlflow

from consentflow.anonymizer import anonymize_record
from consentflow.sdk import is_user_consented

logger = logging.getLogger(__name__)

# ── Result container ───────────────────────────────────────────────────────────


@dataclass
class GateResult:
    """Summary of a single dataset registration run."""

    run_id: str
    total_records: int
    consented_count: int
    anonymized_count: int
    mlflow_run_id: str
    artifact_path: str
    cleaned_dataset: list[dict[str, Any]] = field(default_factory=list)

    @property
    def filtered_count(self) -> int:
        """Alias: number of records that were anonymized (revoked users)."""
        return self.anonymized_count

    def summary(self) -> str:  # pragma: no cover
        lines = [
            f"+-- MLflow Run {self.mlflow_run_id[:8]}... " + "-" * 38,
            f"|  Pipeline run_id   : {self.run_id}",
            f"|  Total records     : {self.total_records}",
            f"|  Consented (pass)  : {self.consented_count}",
            f"|  Anonymized (block): {self.anonymized_count}",
            f"|  Artifact          : {self.artifact_path}",
            "+" + "-" * 58,
        ]
        return "\n".join(lines)


# ── Core gate function ─────────────────────────────────────────────────────────


async def register_dataset_with_consent_check(
    dataset: list[dict[str, Any]],
    run_id: str,
    *,
    purpose: str = "model_training",
    redis_client: Any = None,
    db_pool: Any = None,
    mlflow_experiment: str = "ConsentFlow / Dataset Gate",
) -> GateResult:
    """
    Iterate over *dataset*, enforce consent, anonymize revoked records, and
    log results to MLflow.

    Parameters
    ----------
    dataset:   List of record dicts.  Each record **must** contain a ``user_id``
               key whose value is a UUID string.
    run_id:    Identifier for this pipeline run (used as an MLflow tag and
               artifact path prefix).
    purpose:   Consent purpose to check (default: ``'model_training'``).
    redis_client: Optional shared Redis client (injected by tests / app layer).
    db_pool:   Optional shared asyncpg pool (injected by tests / app layer).
    mlflow_experiment: MLflow experiment name.

    Returns
    -------
    GateResult with counts and the cleaned dataset.
    """
    logger.info(
        "Dataset gate started — run_id=%s  records=%d  purpose=%s",
        run_id,
        len(dataset),
        purpose,
    )

    cleaned: list[dict[str, Any]] = []
    anonymized_count = 0
    consented_count = 0

    for record in dataset:
        uid = str(record.get("user_id", ""))
        if not uid:
            logger.warning("Record missing user_id — treating as revoked: %s", record)
            cleaned.append(anonymize_record(record))
            anonymized_count += 1
            continue

        consented = await is_user_consented(
            uid,
            purpose,
            redis_client=redis_client,
            db_pool=db_pool,
        )

        if consented:
            consented_count += 1
            cleaned.append(record)
            logger.debug("PASS   user_id=%s", uid)
        else:
            anonymized_count += 1
            cleaned.append(anonymize_record(record))
            logger.info("ANON   user_id=%s — consent revoked or absent", uid)

    total = len(dataset)
    logger.info(
        "Dataset gate complete — total=%d  consented=%d  anonymized=%d",
        total,
        consented_count,
        anonymized_count,
    )

    # ── MLflow logging ────────────────────────────────────────────────────────
    mlflow.set_experiment(mlflow_experiment)

    with mlflow.start_run(run_name=run_id) as active_run:
        mlflow_run_id = active_run.info.run_id

        # Log scalar metrics
        mlflow.log_metrics(
            {
                "total_records": total,
                "consented_count": consented_count,
                "anonymized_count": anonymized_count,
                "anonymized_ratio": anonymized_count / total if total else 0.0,
            }
        )

        # Log pipeline run_id as a tag
        mlflow.set_tags(
            {
                "pipeline_run_id": run_id,
                "purpose": purpose,
                "step": "dataset_gate",
            }
        )

        # Dump cleaned dataset to a temp JSON file then log as artifact
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_file = pathlib.Path(tmpdir) / f"{run_id}_cleaned_dataset.json"
            artifact_file.write_text(
                json.dumps(cleaned, indent=2, default=str),
                encoding="utf-8",
            )
            mlflow.log_artifact(str(artifact_file), artifact_path="dataset_gate")
            artifact_path = f"dataset_gate/{artifact_file.name}"

        logger.info("MLflow run %s logged — artifact=%s", mlflow_run_id, artifact_path)

    return GateResult(
        run_id=run_id,
        total_records=total,
        consented_count=consented_count,
        anonymized_count=anonymized_count,
        mlflow_run_id=mlflow_run_id,
        artifact_path=artifact_path,
        cleaned_dataset=cleaned,
    )
