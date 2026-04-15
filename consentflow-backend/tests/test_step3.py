"""
tests/test_step3.py — Integration test for Step 3 (Dataset Gate).

Scenario
--------
5 synthetic users are generated.  2 of them (index 1 and 3) have their consent
marked as 'revoked' in an in-memory consent store.  The other 3 have 'granted'.

The dataset is run through ``register_dataset_with_consent_check()`` with all
network calls (Redis, Postgres) replaced by lightweight in-process fakes so
the test requires no running infrastructure.

Expected outcome
----------------
* ``consented_count``  == 3 (pass-through, PII intact)
* ``anonymized_count`` == 2 (records anonymized by Presidio)
* The MLflow run is created and its summary is printed to stdout.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from consentflow.dataset_gate import register_dataset_with_consent_check

logger = logging.getLogger(__name__)

# ── Synthetic dataset ──────────────────────────────────────────────────────────

# 5 users — indices 1 and 3 will have consent revoked
_USER_IDS = [str(uuid4()) for _ in range(5)]
_REVOKED_INDICES = {1, 3}  # users at these positions have revoked consent

DATASET: list[dict[str, Any]] = [
    {
        "user_id": _USER_IDS[0],
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "phone": "+1-202-555-0147",
        "diagnosis": "Type 2 diabetes",
        "score": 0.87,
    },
    {
        "user_id": _USER_IDS[1],  # REVOKED
        "name": "Bob Smith",
        "email": "bob@example.com",
        "phone": "+44 20 7946 0958",
        "diagnosis": "Hypertension",
        "score": 0.62,
    },
    {
        "user_id": _USER_IDS[2],
        "name": "Carol Davis",
        "email": "carol@example.com",
        "phone": "+1-800-555-1234",
        "diagnosis": "Asthma",
        "score": 0.91,
    },
    {
        "user_id": _USER_IDS[3],  # REVOKED
        "name": "David Lee",
        "email": "david@example.com",
        "phone": "+1-877-555-9999",
        "diagnosis": "Migraine",
        "score": 0.74,
    },
    {
        "user_id": _USER_IDS[4],
        "name": "Eve Martinez",
        "email": "eve@example.com",
        "phone": "+1-415-555-7890",
        "diagnosis": "Insomnia",
        "score": 0.55,
    },
]


# ── Consent lookup mock ────────────────────────────────────────────────────────

def _make_consent_lookup(revoked_user_ids: set[str]):
    """
    Return an async mock for ``is_user_consented`` that uses an in-memory map.
    Users whose ID is in *revoked_user_ids* return False; all others return True.
    """
    async def _mock_is_user_consented(
        user_id: str,
        purpose: str,
        *,
        redis_client=None,
        db_pool=None,
    ) -> bool:
        consented = str(user_id) not in revoked_user_ids
        logger.debug("mock consent check user_id=%s → %s", user_id, consented)
        return consented

    return _mock_is_user_consented


# ── Test ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dataset_gate_step3():
    """
    Run the dataset gate with 5 records (2 revoked) and verify the outcome.
    Prints the full MLflow run summary to stdout.
    """
    revoked_ids = {_USER_IDS[i] for i in _REVOKED_INDICES}

    # Patch is_user_consented inside dataset_gate so no real network calls occur
    with patch(
        "consentflow.dataset_gate.is_user_consented",
        side_effect=_make_consent_lookup(revoked_ids),
    ):
        result = await register_dataset_with_consent_check(
            dataset=DATASET,
            run_id="test-run-step3",
            purpose="model_training",
        )

    # ── Assertions ─────────────────────────────────────────────────────────────
    assert result.total_records == 5, f"Expected 5 total, got {result.total_records}"
    assert result.consented_count == 3, f"Expected 3 consented, got {result.consented_count}"
    assert result.anonymized_count == 2, f"Expected 2 anonymized, got {result.anonymized_count}"
    assert len(result.cleaned_dataset) == 5, "Cleaned dataset should still have 5 records"

    # Consented users should keep their PII intact
    consented_indices = [i for i in range(5) if i not in _REVOKED_INDICES]
    for idx in consented_indices:
        original = DATASET[idx]
        cleaned = result.cleaned_dataset[idx]
        assert cleaned["user_id"] == original["user_id"]
        # Score (numeric) should be untouched no matter what
        assert cleaned["score"] == original["score"]

    # Revoked users must have had their string fields processed by Presidio
    for idx in _REVOKED_INDICES:
        original = DATASET[idx]
        cleaned = result.cleaned_dataset[idx]
        # Name and email strings must differ from the originals
        # (Presidio replaces them with <REDACTED> tags)
        assert cleaned.get("name") != original["name"], (
            f"Name was NOT anonymized for revoked user at index {idx}: {cleaned.get('name')}"
        )
        assert cleaned.get("email") != original["email"], (
            f"Email was NOT anonymized for revoked user at index {idx}: {cleaned.get('email')}"
        )

    # ── Print MLflow run summary ───────────────────────────────────────────────
    print()
    print(result.summary())
    print()
    print("Cleaned dataset preview:")
    for i, record in enumerate(result.cleaned_dataset):
        status_tag = "PASS" if i not in _REVOKED_INDICES else "ANON"
        print(f"  [{status_tag}] record[{i}]: {json.dumps(record, default=str)}")
