"""
tests/test_policy_auditor.py — Gate 05: Policy Auditor unit test suite.

All tests are fully isolated:
  - No real Ollama calls (httpx.AsyncClient is mocked).
  - No real HTTP requests to policy URLs (httpx.AsyncClient is mocked).
  - No real database (FakePool / FakeConnection from conftest).
  - No real Redis (FakeRedis from conftest).

Test IDs
--------
test_analyze_policy_returns_findings         — happy path: 1 critical finding
test_analyze_policy_empty_findings           — empty findings → risk "low"
test_analyze_policy_strips_markdown_fences   — ```json fence stripped before parse
test_analyze_policy_invalid_json_raises      — non-JSON → ValueError raised
test_analyze_policy_unknown_severity_defaults_to_low — severity "banana" → "low"
test_fetch_policy_text_success               — HTTP 200 → returns text
test_fetch_policy_text_http_error            — HTTP 404 → httpx.HTTPError propagates
test_ollama_timeout_raises                   — TimeoutException propagates out
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from consentflow.policy_auditor import (
    PolicyAuditor,
    PolicyFetchError,
    analyze_policy,
    fetch_policy_text,
)
from consentflow.app.models import PolicyScanRequest, PolicyScanResult, PolicyFinding


# ── Shared fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def fake_pool(fake_pool):  # noqa: F811
    return fake_pool


@pytest.fixture
def fake_redis(fake_redis):  # noqa: F811
    return fake_redis


@pytest.fixture
def fake_settings():
    """Minimal settings stub for unit tests."""
    s = MagicMock()
    s.ollama_base_url = "http://localhost:11434"
    s.ollama_model = "qwen3:8b"
    return s


def _make_auditor(fake_pool, fake_redis) -> PolicyAuditor:
    """Construct a PolicyAuditor (no api_key needed anymore)."""
    return PolicyAuditor(db_pool=fake_pool, redis_client=fake_redis)


def _make_ollama_response(payload: dict) -> MagicMock:
    """
    Build a MagicMock that mimics an httpx.Response from POST /v1/chat/completions.

    .json() returns the OpenAI-compatible envelope wrapping the JSON payload.
    .raise_for_status() is a no-op (200 OK).
    """
    envelope = {
        "choices": [
            {"message": {"content": json.dumps(payload)}}
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = envelope
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ── Test 1: happy path — 1 critical finding ───────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_policy_returns_findings(fake_settings):
    """LLM returns 1 critical finding → analyze_policy surfaces it correctly."""
    payload = {
        "findings": [
            {
                "id": "finding_1",
                "severity": "critical",
                "category": "Training on Inputs",
                "clause_excerpt": "We may train on your inputs without notice.",
                "explanation": "Model training on user data without consent.",
                "article_reference": "GDPR Article 6(1)",
            }
        ],
        "overall_risk_level": "critical",
        "raw_summary": "One critical training clause found.",
    }

    mock_resp = _make_ollama_response(payload)

    with patch("consentflow.policy_auditor.httpx.AsyncClient") as MockClient:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.post = AsyncMock(return_value=mock_resp)
        MockClient.return_value = mock_ctx

        findings, raw_summary, risk_level = await analyze_policy(
            "We may train on your inputs without notice.",
            "TestPlugin",
            fake_settings,
        )

    assert risk_level == "critical"
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"
    assert findings[0]["category"] == "Training on Inputs"
    assert "critical" in raw_summary.lower()


# ── Test 2: empty findings → risk "low" ───────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_policy_empty_findings(fake_settings):
    """LLM returns empty findings array → overall_risk_level must be 'low'."""
    payload = {
        "findings": [],
        "overall_risk_level": "low",
        "raw_summary": "No red flags detected.",
    }

    mock_resp = _make_ollama_response(payload)

    with patch("consentflow.policy_auditor.httpx.AsyncClient") as MockClient:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.post = AsyncMock(return_value=mock_resp)
        MockClient.return_value = mock_ctx

        findings, raw_summary, risk_level = await analyze_policy(
            "We collect only minimum data.", "CleanPlugin", fake_settings
        )

    assert risk_level == "low"
    assert findings == []


# ── Test 3: markdown fences stripped before parse ─────────────────────────────


@pytest.mark.asyncio
async def test_analyze_policy_strips_markdown_fences(fake_settings):
    """LLM wraps JSON in ```json ... ``` — must still parse correctly."""
    inner_payload = {
        "findings": [],
        "overall_risk_level": "low",
        "raw_summary": "No issues found.",
    }
    fenced_content = f"```json\n{json.dumps(inner_payload)}\n```"

    envelope = {"choices": [{"message": {"content": fenced_content}}]}
    mock_resp = MagicMock()
    mock_resp.json.return_value = envelope
    mock_resp.raise_for_status = MagicMock()

    with patch("consentflow.policy_auditor.httpx.AsyncClient") as MockClient:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.post = AsyncMock(return_value=mock_resp)
        MockClient.return_value = mock_ctx

        findings, raw_summary, risk_level = await analyze_policy(
            "Policy text.", "FencePlugin", fake_settings
        )

    assert risk_level == "low"
    assert findings == []


# ── Test 4: non-JSON response → ValueError raised ─────────────────────────────


@pytest.mark.asyncio
async def test_analyze_policy_invalid_json_raises(fake_settings):
    """LLM returns plain text instead of JSON → ValueError must propagate."""
    envelope = {
        "choices": [{"message": {"content": "Sorry, I cannot help with that."}}]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = envelope
    mock_resp.raise_for_status = MagicMock()

    with patch("consentflow.policy_auditor.httpx.AsyncClient") as MockClient:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.post = AsyncMock(return_value=mock_resp)
        MockClient.return_value = mock_ctx

        with pytest.raises(ValueError):
            await analyze_policy("Policy text.", "BadPlugin", fake_settings)


# ── Test 5: unknown severity → coerced to "low" ───────────────────────────────


@pytest.mark.asyncio
async def test_analyze_policy_unknown_severity_defaults_to_low(fake_settings):
    """LLM returns severity='banana' → must be coerced to 'low'."""
    payload = {
        "findings": [
            {
                "id": "finding_1",
                "severity": "banana",        # invalid!
                "category": "Training on Inputs",
                "clause_excerpt": "We train on inputs.",
                "explanation": "Bad severity value from model.",
                "article_reference": "",
            }
        ],
        "overall_risk_level": "banana",      # also invalid
        "raw_summary": "One finding of unknown severity.",
    }

    mock_resp = _make_ollama_response(payload)

    with patch("consentflow.policy_auditor.httpx.AsyncClient") as MockClient:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.post = AsyncMock(return_value=mock_resp)
        MockClient.return_value = mock_ctx

        findings, _, risk_level = await analyze_policy(
            "Policy text.", "WeirdPlugin", fake_settings
        )

    assert findings[0]["severity"] == "low"
    assert risk_level == "low"


# ── Test 6: fetch_policy_text success ────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_policy_text_success(fake_settings):
    """HTTP 200 from a fake URL → returns the plain text body."""
    mock_resp = MagicMock()
    mock_resp.text = "We collect data for service improvement."
    mock_resp.headers = {"content-type": "text/plain"}
    mock_resp.raise_for_status = MagicMock()

    with patch("consentflow.policy_auditor.httpx.AsyncClient") as MockClient:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.get = AsyncMock(return_value=mock_resp)
        MockClient.return_value = mock_ctx

        text = await fetch_policy_text("https://example.com/policy", fake_settings)

    assert "collect data" in text


# ── Test 7: fetch_policy_text HTTP error → httpx.HTTPError propagates ─────────


@pytest.mark.asyncio
async def test_fetch_policy_text_http_error(fake_settings):
    """HTTP 404 from fake URL → httpx.HTTPStatusError must propagate."""
    fake_request = httpx.Request("GET", "https://example.com/missing")
    fake_response = httpx.Response(404, request=fake_request)
    error = httpx.HTTPStatusError(
        "404 Not Found", request=fake_request, response=fake_response
    )

    with patch("consentflow.policy_auditor.httpx.AsyncClient") as MockClient:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.get = AsyncMock(side_effect=error)
        MockClient.return_value = mock_ctx

        with pytest.raises(httpx.HTTPError):
            await fetch_policy_text("https://example.com/missing", fake_settings)


# ── Test 8: Ollama timeout → TimeoutException propagates ──────────────────────


@pytest.mark.asyncio
async def test_ollama_timeout_raises(fake_settings):
    """httpx.TimeoutException raised by mock → must propagate out of analyze_policy."""
    with patch("consentflow.policy_auditor.httpx.AsyncClient") as MockClient:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.post = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        MockClient.return_value = mock_ctx

        with pytest.raises(httpx.TimeoutException):
            await analyze_policy("Policy text.", "SlowPlugin", fake_settings)
