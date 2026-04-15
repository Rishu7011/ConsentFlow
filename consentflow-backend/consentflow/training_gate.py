"""
consentflow/training_gate.py — Kafka consumer that enforces consent at training time.

Purpose
-------
The Training Gate listens on the ``consent.revoked`` Kafka topic (the same topic
written by the webhook ingress in Step 2).  When a revocation event arrives it:

  1. Extracts the ``user_id`` from the event payload.
  2. Searches MLflow for all experiment runs that were trained with that user's
     data (delegating to :mod:`consentflow.mlflow_utils`).
  3. Applies a ``consent_status=quarantined`` tag to each matching run.
  4. Writes a structured quarantine log record (Python structured log + optional
     in-memory list for testing introspection).

It does **not** retrain, delete, or modify any model artefacts.

Running standalone
------------------
    python -m consentflow.training_gate

Or call ``run_training_gate_consumer()`` from application startup code.

Injected dependencies (for testing)
------------------------------------
``TrainingGateConsumer.__init__`` accepts:

* ``consumer``         — an ``AIOKafkaConsumer``-compatible object (any object
                         that supports ``async for msg in consumer``).
* ``search_runs_fn``   — replaces ``mlflow_utils.search_runs_by_user``.
* ``quarantine_fn``    — replaces ``mlflow_utils.apply_quarantine_tags``.

This avoids any real Kafka or MLflow calls in unit tests.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from consentflow.app.config import settings
from consentflow.mlflow_utils import (
    apply_quarantine_tags,
    search_runs_by_user,
)

logger = logging.getLogger(__name__)


# ── Quarantine log record ─────────────────────────────────────────────────────


@dataclass
class QuarantineRecord:
    """
    An immutable record of one quarantine action.

    Attributes
    ----------
    user_id:          UUID of the user whose consent was revoked.
    run_id:           MLflow run ID that was flagged.
    experiment_id:    MLflow experiment the run belongs to.
    flagged_at:       ISO-8601 UTC timestamp when the flag was applied.
    reason:           Human-readable reason (default: ``"consent_revoked"``).
    kafka_offset:     Offset of the Kafka message that triggered this action.
    kafka_partition:  Partition of the Kafka message.
    """

    user_id: str
    run_id: str
    experiment_id: str
    flagged_at: str
    reason: str = "consent_revoked"
    kafka_offset: int = -1
    kafka_partition: int = -1

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "flagged_at": self.flagged_at,
            "reason": self.reason,
            "kafka_offset": self.kafka_offset,
            "kafka_partition": self.kafka_partition,
        }


# ── Consumer class ────────────────────────────────────────────────────────────


class TrainingGateConsumer:
    """
    Asynchronous Kafka consumer that quarantines MLflow runs on consent revocation.

    Parameters
    ----------
    consumer:       Async-iterable Kafka consumer (e.g. ``AIOKafkaConsumer``).
                    Must yield message objects with ``.value`` (bytes or dict),
                    ``.offset`` (int), and ``.partition`` (int) attributes.
    search_runs_fn: Callable to discover MLflow runs for a given ``user_id``.
                    Signature: ``(user_id: str) -> list[Run]``.
                    Defaults to :func:`~consentflow.mlflow_utils.search_runs_by_user`.
    quarantine_fn:  Callable to apply quarantine tags to a single run.
                    Signature: ``(run_id: str, user_id: str, *, ...) -> None``.
                    Defaults to :func:`~consentflow.mlflow_utils.apply_quarantine_tags`.
    """

    def __init__(
        self,
        consumer: Any,
        *,
        search_runs_fn: Callable[..., Any] | None = None,
        quarantine_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._consumer = consumer
        self._search_runs = search_runs_fn or search_runs_by_user
        self._quarantine = quarantine_fn or apply_quarantine_tags
        # In-memory log for test introspection; can grow unboundedly in practice
        # — for production, persist to a DB or emit as structured logs instead.
        self.quarantine_log: list[QuarantineRecord] = []

    # ── Message parsing ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_event(raw_value: bytes | dict | str) -> dict[str, Any]:
        """
        Deserialise a Kafka message value into a Python dict.

        Accepts:
        * ``bytes``  — decoded as UTF-8 JSON.
        * ``str``    — parsed as JSON.
        * ``dict``   — passed through as-is (already deserialised).
        """
        if isinstance(raw_value, dict):
            return raw_value
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        return json.loads(raw_value)  # type: ignore[arg-type]

    # ── Core processing ───────────────────────────────────────────────────────

    async def _process_revocation(
        self,
        user_id: str,
        *,
        kafka_offset: int = -1,
        kafka_partition: int = -1,
        timestamp: str | None = None,
    ) -> list[QuarantineRecord]:
        """
        Handle a single revocation event for *user_id*.

        Steps
        -----
        1. Search MLflow runs referencing *user_id*.
        2. For each run, apply quarantine tags (via ``asyncio.to_thread``).
        3. Append a :class:`QuarantineRecord` to ``self.quarantine_log``.

        Returns
        -------
        List of :class:`QuarantineRecord` objects created by this call.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        logger.info(
            "Training gate: processing revocation — user_id=%s  offset=%d  partition=%d",
            user_id,
            kafka_offset,
            kafka_partition,
        )

        # ── 1. Find affected runs ─────────────────────────────────────────────
        try:
            runs = await asyncio.to_thread(self._search_runs, user_id)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Training gate: MLflow search error — user_id=%s  error=%s",
                user_id,
                exc,
            )
            runs = []

        if not runs:
            logger.info(
                "Training gate: no MLflow runs found for user_id=%s — nothing to quarantine",
                user_id,
            )
            return []

        records: list[QuarantineRecord] = []

        for run in runs:
            run_id = run.info.run_id
            exp_id = run.info.experiment_id

            # ── 2. Apply quarantine tags ──────────────────────────────────────
            try:
                await asyncio.to_thread(
                    self._quarantine,
                    run_id,
                    user_id,
                    reason="consent_revoked",
                    timestamp=ts,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Training gate: failed to quarantine run_id=%s  user_id=%s  error=%s",
                    run_id,
                    user_id,
                    exc,
                )
                continue

            # ── 3. Build & store quarantine record ────────────────────────────
            record = QuarantineRecord(
                user_id=user_id,
                run_id=run_id,
                experiment_id=exp_id,
                flagged_at=ts,
                reason="consent_revoked",
                kafka_offset=kafka_offset,
                kafka_partition=kafka_partition,
            )
            self.quarantine_log.append(record)
            records.append(record)

            logger.info(
                "Training gate: QUARANTINED — run_id=%s  exp=%s  user_id=%s  ts=%s",
                run_id,
                exp_id,
                user_id,
                ts,
            )

        return records

    # ── Main consume loop ─────────────────────────────────────────────────────

    async def run(self) -> None:  # pragma: no cover
        """
        Continuously consume ``consent.revoked`` events until cancelled.

        This method is designed to run as a long-lived asyncio task.
        It handles ``asyncio.CancelledError`` gracefully (clean shutdown).
        """
        logger.info(
            "Training gate consumer started — topic=%s  broker=%s",
            settings.kafka_topic_revoke,
            settings.kafka_broker_url,
        )

        try:
            async for msg in self._consumer:
                try:
                    event = self._parse_event(msg.value)
                    user_id: str | None = event.get("user_id")

                    if not user_id:
                        logger.warning(
                            "Training gate: received event without user_id — skipping  "
                            "offset=%d  partition=%d  raw=%s",
                            msg.offset,
                            msg.partition,
                            event,
                        )
                        continue

                    await self._process_revocation(
                        str(user_id),
                        kafka_offset=msg.offset,
                        kafka_partition=msg.partition,
                        timestamp=event.get("timestamp"),
                    )

                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Training gate: unhandled error processing message — "
                        "offset=%d  error=%s",
                        getattr(msg, "offset", -1),
                        exc,
                        exc_info=True,
                    )
        except asyncio.CancelledError:
            logger.info("Training gate consumer: cancelled — shutting down")
            raise


# ── Factory + entry point ─────────────────────────────────────────────────────


async def run_training_gate_consumer() -> None:  # pragma: no cover
    """
    Create a real ``AIOKafkaConsumer`` and run the training gate loop.

    Import this function in your FastAPI lifespan or call it from a standalone
    script.  It runs until the task is cancelled.
    """
    from aiokafka import AIOKafkaConsumer  # imported lazily to ease unit testing

    consumer = AIOKafkaConsumer(
        settings.kafka_topic_revoke,
        bootstrap_servers=settings.kafka_broker_url,
        group_id="consentflow-training-gate",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: v,  # raw bytes; _parse_event handles decoding
    )
    await consumer.start()
    try:
        gate = TrainingGateConsumer(consumer)
        await gate.run()
    finally:
        await consumer.stop()
        logger.info("Training gate consumer: Kafka consumer stopped")


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_training_gate_consumer())
