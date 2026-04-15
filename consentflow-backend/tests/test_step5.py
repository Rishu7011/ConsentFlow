"""
tests/test_step5.py — Unit tests for Step 5 (Training Gate).

Three scenarios tested
----------------------
1. Mock a Kafka ``consent.revoked`` event for a user and verify the correct
   MLflow runs are found and flagged as quarantined.
2. Verify each quarantined run has the expected MLflow tags applied.
3. Verify a :class:`QuarantineRecord` is created with the correct fields for
   every run that was flagged.

Design principles
-----------------
* No real Kafka broker or MLflow tracking server is required.
* ``search_runs_fn`` and ``quarantine_fn`` are replaced with lightweight
  in-memory fakes injected via the ``TrainingGateConsumer`` constructor.
* ``mlflow_utils`` functions are tested independently using the MLflow
  file-based tracking URI so they exercise the real MLflow client code
  without a remote server.
"""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import mlflow
import pytest

from consentflow.mlflow_utils import (
    CONSENT_STATUS_TAG,
    QUARANTINE_REASON_TAG,
    QUARANTINE_TIMESTAMP_TAG,
    QUARANTINED_VALUE,
    REVOKED_USER_TAG,
    STEP_TAG,
    TRAINING_GATE_STEP,
    apply_quarantine_tags,
    list_quarantined_runs,
    search_runs_by_user,
)
from consentflow.training_gate import QuarantineRecord, TrainingGateConsumer

logger = logging.getLogger(__name__)

# ── Synthetic data ─────────────────────────────────────────────────────────────

USER_A = str(uuid4())   # revoked user — will trigger quarantine
USER_B = str(uuid4())   # unrelated user — should NOT be quarantined


# ── Fake Kafka message ─────────────────────────────────────────────────────────


@dataclass
class FakeKafkaMessage:
    """Mimics the interface of an ``aiokafka`` ``ConsumerRecord``."""

    value: bytes | dict | str
    offset: int = 0
    partition: int = 0
    topic: str = "consent.revoked"


# ── Async iterable Kafka consumer stub ────────────────────────────────────────


class FakeKafkaConsumer:
    """
    Async iterable that yields a predetermined list of FakeKafkaMessages, then
    stops.  Allows ``TrainingGateConsumer.run()`` to terminate naturally in
    tests without needing a CancelledError.
    """

    def __init__(self, messages: list[FakeKafkaMessage]) -> None:
        self._messages = messages

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for msg in self._messages:
            yield msg


# ── Fake MLflow run stub ───────────────────────────────────────────────────────


@dataclass
class FakeRunInfo:
    run_id: str
    experiment_id: str = "0"


@dataclass
class FakeRunData:
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class FakeRun:
    info: FakeRunInfo
    data: FakeRunData = field(default_factory=FakeRunData)


# ── Scenario 1 & 3: Kafka event triggers quarantine ───────────────────────────


class TestTrainingGateConsumer:
    """Tests for :class:`~consentflow.training_gate.TrainingGateConsumer`."""

    def _make_revocation_event(self, user_id: str, purpose: str = "model_training") -> bytes:
        """Return a JSON-encoded ``consent.revoked`` Kafka message value."""
        return json.dumps(
            {
                "event": "consent.revoked",
                "user_id": user_id,
                "purpose": purpose,
                "timestamp": "2026-04-08T00:00:00+00:00",
            }
        ).encode("utf-8")

    # ── Shared fakes ───────────────────────────────────────────────────────────

    def _setup_fakes(self, user_id: str) -> tuple[list[FakeRun], list[dict]]:
        """
        Build a fake search function (returns two runs for *user_id*) and a fake
        quarantine function that records its calls.
        """
        run_1 = FakeRun(info=FakeRunInfo(run_id="run-aaa-111", experiment_id="10"))
        run_2 = FakeRun(info=FakeRunInfo(run_id="run-bbb-222", experiment_id="10"))
        fake_runs = [run_1, run_2]

        quarantine_calls: list[dict] = []

        def fake_search(uid: str, **kwargs) -> list[FakeRun]:
            return fake_runs if uid == user_id else []

        def fake_quarantine(run_id: str, uid: str, *, reason: str = "consent_revoked", timestamp: str | None = None) -> None:
            quarantine_calls.append(
                {"run_id": run_id, "user_id": uid, "reason": reason, "timestamp": timestamp}
            )

        return fake_runs, quarantine_calls, fake_search, fake_quarantine

    # ── Scenario 1: Kafka event → runs found and quarantined ──────────────────

    @pytest.mark.asyncio
    async def test_kafka_event_triggers_quarantine(self):
        """
        SCENARIO 1
        ----------
        A Kafka ``consent.revoked`` event arrives for USER_A.
        The consumer should:
          (a) parse the event,
          (b) call ``search_runs_fn`` with USER_A's ID,
          (c) call ``quarantine_fn`` once per found run.
        """
        fake_runs, quarantine_calls, fake_search, fake_quarantine = self._setup_fakes(USER_A)

        msg = FakeKafkaMessage(
            value=self._make_revocation_event(USER_A),
            offset=42,
            partition=0,
        )
        consumer_stub = FakeKafkaConsumer([msg])

        gate = TrainingGateConsumer(
            consumer_stub,
            search_runs_fn=fake_search,
            quarantine_fn=fake_quarantine,
        )
        await gate.run()

        # (b) Both fake runs must have been quarantined
        quarantined_run_ids = {c["run_id"] for c in quarantine_calls}
        assert "run-aaa-111" in quarantined_run_ids, "run-aaa-111 was not quarantined"
        assert "run-bbb-222" in quarantined_run_ids, "run-bbb-222 was not quarantined"

        # (c) Every quarantine call referenced USER_A
        for call in quarantine_calls:
            assert call["user_id"] == USER_A
            assert call["reason"] == "consent_revoked"

        logger.info(
            "Scenario 1 PASS — %d run(s) quarantined for user_id=%s",
            len(quarantine_calls),
            USER_A,
        )

    # ── Scenario 2: Correct MLflow tags are applied ───────────────────────────

    @pytest.mark.asyncio
    async def test_quarantine_tags_are_correct(self):
        """
        SCENARIO 2
        ----------
        Verify that *exactly the right tags* are recorded by the quarantine
        function when a revocation event is processed.

        The quarantine call must supply:
          * ``run_id``   matching the MLflow run
          * ``user_id``  matching USER_A
          * ``reason``   == "consent_revoked"
          * ``timestamp`` non-empty string
        """
        fake_runs, quarantine_calls, fake_search, fake_quarantine = self._setup_fakes(USER_A)

        event_ts = "2026-04-08T00:00:00+00:00"
        msg = FakeKafkaMessage(
            value=json.dumps(
                {
                    "event": "consent.revoked",
                    "user_id": USER_A,
                    "purpose": "model_training",
                    "timestamp": event_ts,
                }
            ).encode(),
            offset=7,
            partition=1,
        )
        consumer_stub = FakeKafkaConsumer([msg])
        gate = TrainingGateConsumer(
            consumer_stub,
            search_runs_fn=fake_search,
            quarantine_fn=fake_quarantine,
        )
        await gate.run()

        assert len(quarantine_calls) == 2, (
            f"Expected 2 quarantine calls (one per run), got {len(quarantine_calls)}"
        )

        for call in quarantine_calls:
            assert call["reason"] == "consent_revoked"
            # Timestamp forwarded from the Kafka event
            assert call["timestamp"] == event_ts, (
                f"Expected timestamp={event_ts!r}, got {call['timestamp']!r}"
            )

        logger.info("Scenario 2 PASS — quarantine call tags validated for user_id=%s", USER_A)

    # ── Scenario 3: QuarantineRecord is created correctly ─────────────────────

    @pytest.mark.asyncio
    async def test_quarantine_log_record_is_created(self):
        """
        SCENARIO 3
        ----------
        Verify that a :class:`QuarantineRecord` is appended to
        ``gate.quarantine_log`` for every quarantined run and that each record
        carries the expected field values.
        """
        fake_runs, quarantine_calls, fake_search, fake_quarantine = self._setup_fakes(USER_A)

        msg = FakeKafkaMessage(
            value=self._make_revocation_event(USER_A),
            offset=99,
            partition=3,
        )
        consumer_stub = FakeKafkaConsumer([msg])
        gate = TrainingGateConsumer(
            consumer_stub,
            search_runs_fn=fake_search,
            quarantine_fn=fake_quarantine,
        )
        await gate.run()

        log = gate.quarantine_log
        assert len(log) == 2, f"Expected 2 QuarantineRecord(s), got {len(log)}"

        run_ids_in_log = {r.run_id for r in log}
        assert "run-aaa-111" in run_ids_in_log
        assert "run-bbb-222" in run_ids_in_log

        for record in log:
            assert isinstance(record, QuarantineRecord), "Log entry is not a QuarantineRecord"
            assert record.user_id == USER_A
            assert record.experiment_id == "10"
            assert record.reason == "consent_revoked"
            assert record.kafka_offset == 99
            assert record.kafka_partition == 3
            # flagged_at must be a non-empty string
            assert record.flagged_at, "flagged_at must not be empty"

            # Ensure to_dict() round-trip works
            d = record.to_dict()
            assert d["user_id"] == USER_A
            assert d["run_id"] == record.run_id
            assert d["reason"] == "consent_revoked"

        logger.info(
            "Scenario 3 PASS — %d QuarantineRecord(s) validated for user_id=%s",
            len(log),
            USER_A,
        )

    # ── Edge case: no runs found → no quarantine ──────────────────────────────

    @pytest.mark.asyncio
    async def test_no_runs_no_quarantine(self):
        """
        If MLflow has no runs for the revoked user, no quarantine calls should
        be made and the log should remain empty.
        """
        quarantine_calls: list[dict] = []

        def fake_search(uid: str, **kwargs):
            return []  # nothing found

        def fake_quarantine(run_id: str, uid: str, **kwargs):
            quarantine_calls.append({"run_id": run_id})

        msg = FakeKafkaMessage(
            value=json.dumps({"event": "consent.revoked", "user_id": USER_B}).encode(),
            offset=0,
            partition=0,
        )
        gate = TrainingGateConsumer(
            FakeKafkaConsumer([msg]),
            search_runs_fn=fake_search,
            quarantine_fn=fake_quarantine,
        )
        await gate.run()

        assert quarantine_calls == [], "No quarantine calls expected when no runs found"
        assert gate.quarantine_log == []
        logger.info("Edge case PASS — no quarantine when no runs found for user_id=%s", USER_B)

    # ── Edge case: missing user_id in event ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_event_without_user_id_is_skipped(self):
        """
        A malformed event missing 'user_id' must be silently skipped (no crash,
        no quarantine call).
        """
        quarantine_calls: list = []

        gate = TrainingGateConsumer(
            FakeKafkaConsumer(
                [FakeKafkaMessage(value=json.dumps({"event": "consent.revoked"}).encode())]
            ),
            search_runs_fn=lambda uid, **kw: [],
            quarantine_fn=lambda *a, **kw: quarantine_calls.append(a),
        )
        await gate.run()

        assert quarantine_calls == []
        logger.info("Edge case PASS — malformed event (no user_id) skipped without error")

    # ── Dict-valued message (already-deserialised) ────────────────────────────

    @pytest.mark.asyncio
    async def test_dict_message_value_is_parsed(self):
        """
        AIOKafkaConsumer can be configured with a JSON deserialiser that returns
        a Python dict.  ``_parse_event`` must handle this transparently.
        """
        fake_runs, quarantine_calls, fake_search, fake_quarantine = self._setup_fakes(USER_A)

        msg = FakeKafkaMessage(
            value={"event": "consent.revoked", "user_id": USER_A, "purpose": "analytics"},
            offset=1,
            partition=0,
        )
        gate = TrainingGateConsumer(
            FakeKafkaConsumer([msg]),
            search_runs_fn=fake_search,
            quarantine_fn=fake_quarantine,
        )
        await gate.run()

        assert len(quarantine_calls) == 2
        logger.info("Edge case PASS — dict-valued Kafka message parsed correctly")


# ── mlflow_utils integration tests ────────────────────────────────────────────


class TestMlflowUtils:
    """
    Tests for :mod:`~consentflow.mlflow_utils` functions.

    Uses a temporary local MLflow tracking directory so no server is required.
    """

    @pytest.fixture(autouse=True)
    def _use_temp_mlflow(self, tmp_path):
        """Set MLflow to use a temporary local directory for the test session."""
        tracking_uri = tmp_path.as_uri()
        mlflow.set_tracking_uri(tracking_uri)
        yield
        # Reset back to default after the test
        mlflow.set_tracking_uri("")

    def _create_run_with_tags(self, experiment_name: str, tags: dict[str, str]) -> str:
        """Helper: create an MLflow run with the given tags and return its run_id."""
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run() as run:
            mlflow.set_tags(tags)
            return run.info.run_id

    # ── apply_quarantine_tags ─────────────────────────────────────────────────

    def test_apply_quarantine_tags_sets_correct_tags(self):
        """``apply_quarantine_tags`` must write all required tags to the run."""
        run_id = self._create_run_with_tags("test-exp", {"step": "dataset_gate"})

        apply_quarantine_tags(run_id, USER_A, reason="consent_revoked", timestamp="2026-01-01T00:00:00+00:00")

        client = mlflow.tracking.MlflowClient()
        run = client.get_run(run_id)
        tags = run.data.tags

        assert tags[CONSENT_STATUS_TAG] == QUARANTINED_VALUE
        assert tags[REVOKED_USER_TAG] == USER_A
        assert tags[QUARANTINE_REASON_TAG] == "consent_revoked"
        assert tags[QUARANTINE_TIMESTAMP_TAG] == "2026-01-01T00:00:00+00:00"
        assert tags[STEP_TAG] == TRAINING_GATE_STEP
        logger.info("apply_quarantine_tags PASS — all tags verified for run_id=%s", run_id)

    # ── list_quarantined_runs ─────────────────────────────────────────────────

    def test_list_quarantined_runs_returns_tagged_runs(self):
        """``list_quarantined_runs`` must return only runs flagged as quarantined."""
        # Create 2 quarantined runs and 1 clean run
        run_q1 = self._create_run_with_tags("test-exp", {})
        run_q2 = self._create_run_with_tags("test-exp", {})
        run_clean = self._create_run_with_tags("test-exp", {"step": "dataset_gate"})

        apply_quarantine_tags(run_q1, USER_A)
        apply_quarantine_tags(run_q2, USER_B)

        quarantined = list_quarantined_runs()
        quarantined_ids = {r.info.run_id for r in quarantined}

        assert run_q1 in quarantined_ids, "q1 should be in quarantine list"
        assert run_q2 in quarantined_ids, "q2 should be in quarantine list"
        assert run_clean not in quarantined_ids, "clean run must NOT appear in quarantine list"
        logger.info(
            "list_quarantined_runs PASS — found %d quarantined runs (expected ≥ 2)",
            len(quarantined),
        )

    # ── search_runs_by_user ───────────────────────────────────────────────────

    def test_search_runs_by_user_finds_tagged_run(self):
        """``search_runs_by_user`` must return runs already tagged with ``revoked_user``."""
        run_id = self._create_run_with_tags(
            "test-exp",
            {REVOKED_USER_TAG: USER_A},
        )

        found = search_runs_by_user(USER_A)
        found_ids = {r.info.run_id for r in found}

        assert run_id in found_ids, (
            f"Expected run_id={run_id} in search results, got {found_ids}"
        )
        logger.info("search_runs_by_user PASS — found tagged run for user_id=%s", USER_A)

    def test_search_runs_by_user_no_match_returns_empty(self):
        """``search_runs_by_user`` must return an empty list when no runs match."""
        unknown_user = str(uuid4())
        found = search_runs_by_user(unknown_user)
        assert found == [], f"Expected empty list, got {found}"
        logger.info("search_runs_by_user PASS — empty result for unknown user")
