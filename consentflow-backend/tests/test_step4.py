"""
tests/test_step4.py — Integration tests for Step 4 (Inference Gate).

Tests the 3 requested scenarios:
1. Valid consent → 200 (pass through)
2. Revoked consent → 403 (blocked)
3. Missing user_id → 400
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

# We use the same UUID from test_consent.py for our mock setup
USER_VALID = "550e8400-e29b-41d4-a716-446655440000"
USER_REVOKED = "11111111-2222-3333-4444-555555555555"

@pytest.fixture
def mock_is_user_consented(monkeypatch):
    """
    Patch the sdk.is_user_consented function so we do not actually
    hit the database or redis, keeping tests perfectly isolated.
    """
    async def _mock_check(user_id: str, purpose: str, **kwargs) -> bool:
        if str(user_id) == USER_REVOKED:
            return False
        return True

    monkeypatch.setattr(
        "consentflow.inference_gate.is_user_consented",
        _mock_check,
    )


@pytest.mark.asyncio
async def test_inference_gate_missing_user_id(client: AsyncClient, mock_is_user_consented):
    """Scenario 3: Missing user_id block."""
    # POST to /infer/predict with missing X-User-ID and blank body
    response = await client.post("/infer/predict", json={"some_other_field": "hello"})
    
    assert response.status_code == 400
    assert "Missing user identifier" in response.json()["error"]


@pytest.mark.asyncio
async def test_inference_gate_revoked_consent(client: AsyncClient, mock_is_user_consented):
    """Scenario 2: User with revoked consent is blocked."""
    # Provide the revoked UUID in the body
    response = await client.post(
        "/infer/predict", 
        json={"user_id": USER_REVOKED}
    )
    
    assert response.status_code == 403
    payload = response.json()
    assert "consent revoked" in payload["error"]
    assert payload["user_id"] == USER_REVOKED


@pytest.mark.asyncio
async def test_inference_gate_valid_consent(client: AsyncClient, mock_is_user_consented):
    """Scenario 1: User with valid consent passes through."""
    # Provide the valid UUID in a header
    response = await client.post(
        "/infer/predict", 
        headers={"X-User-ID": USER_VALID},
        json={"prompt": "Translate 'hello' to French."}
    )
    
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["user_id"] == USER_VALID
    assert "dummy_output" in payload["prediction"]
