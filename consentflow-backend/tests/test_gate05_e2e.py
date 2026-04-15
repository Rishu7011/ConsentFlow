"""
tests/test_gate05_e2e.py — Gate 05 (Policy Auditor) end-to-end smoke tests.

These are unit/integration tests that verify the full Gate 05 flow from HTTP
request through LLM analysis and DB persistence — with ALL external I/O mocked.

No real resources are required to run this file:
  - No Ollama running
  - No running PostgreSQL / asyncpg pool
  - No outbound HTTP requests
  - No Redis client

Run with:
    pytest tests/test_gate05_e2e.py -v
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient, Request as HttpxRequest

from consentflow.app.models import PolicyScanRequest, PolicyScanResult, PolicyFinding
from consentflow.policy_auditor import PolicyAuditor, PolicyFetchError


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_ollama_response(findings: list[dict], summary: str, risk_level: str) -> MagicMock:
    """Build a MagicMock that mimics an httpx.Response from POST /v1/chat/completions."""
    payload = {
        "findings": findings,
        "overall_risk_level": risk_level,
        "raw_summary": summary,
    }
    envelope = {"choices": [{"message": {"content": json.dumps(payload)}}]}
    mock_resp = MagicMock()
    mock_resp.json.return_value = envelope
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _make_auditor(fake_pool, fake_redis) -> PolicyAuditor:
    """Construct a PolicyAuditor (no api_key needed)."""
    return PolicyAuditor(db_pool=fake_pool, redis_client=fake_redis)


def _mock_ollama_client(post_return=None, post_side_effect=None, get_return=None, get_side_effect=None):
    """
    Return a context-manager-compatible mock for httpx.AsyncClient.

    Callers can set post_return / post_side_effect for LLM calls and
    get_return / get_side_effect for policy URL fetches.
    """
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    if post_side_effect is not None:
        mock_ctx.post = AsyncMock(side_effect=post_side_effect)
    elif post_return is not None:
        mock_ctx.post = AsyncMock(return_value=post_return)
    if get_side_effect is not None:
        mock_ctx.get = AsyncMock(side_effect=get_side_effect)
    elif get_return is not None:
        mock_ctx.get = AsyncMock(return_value=get_return)
    return mock_ctx


# Reusable finding shapes ──────────────────────────────────────────────────────

FINDING_CRITICAL = {
    "id": "finding_1",
    "severity": "critical",
    "category": "Training on Inputs",
    "clause_excerpt": "we may use your inputs to train our models without additional notice",
    "explanation": (
        "The vendor reserves the right to train models on user inputs "
        "without explicit, separate consent — directly undermining GDPR Art. 6."
    ),
    "article_reference": "GDPR Article 6(1)",
}

FINDING_MEDIUM = {
    "id": "finding_2",
    "severity": "medium",
    "category": "Broad Data Sharing",
    "clause_excerpt": "Data may be shared with our affiliated partners for service improvement.",
    "explanation": "Third-party sharing after consent revocation violates CCPA 1798.120.",
    "article_reference": "CCPA 1798.120",
}


# ── Test 1: Full scan — URL mode ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_scan_flow_url_mode(fake_pool, fake_redis):
    """
    End-to-end scan pipeline in URL mode.

    Mocks:
    - httpx.AsyncClient.get  → returns fake HTML containing a training clause
    - httpx.AsyncClient.post → returns 2 findings (critical + medium), overall "critical"
    - asyncpg pool (FakePool from conftest) — captures execute() calls
    """
    auditor = _make_auditor(fake_pool, fake_redis)

    # ── Mock: HTTP fetch of policy URL ───────────────────────────────────────
    fake_http_response = MagicMock()
    fake_http_response.text = (
        "<html><body>"
        "<p>We may use your inputs to train our models without additional notice.</p>"
        "<p>Data may be shared with affiliated partners for service improvement.</p>"
        "</body></html>"
    )
    fake_http_response.headers = {"content-type": "text/html; charset=utf-8"}
    fake_http_response.raise_for_status = MagicMock()

    # ── Mock: Ollama LLM response ─────────────────────────────────────────────
    ollama_resp = _make_ollama_response(
        [FINDING_CRITICAL, FINDING_MEDIUM],
        "Two findings detected: one critical training clause and one medium sharing clause.",
        "critical",
    )

    # Track asyncpg execute calls
    execute_calls: list[str] = []

    class TrackingConnection:
        async def execute(self, sql: str, *args, **kwargs):
            execute_calls.append(sql.strip())

        async def fetchrow(self, *args, **kwargs):
            return None

        async def fetch(self, *args, **kwargs):
            return []

        async def fetchval(self, *args, **kwargs):
            return 1

    class TrackingPool:
        def acquire(self):
            return self

        async def __aenter__(self):
            return TrackingConnection()

        async def __aexit__(self, *args):
            pass

    tracking_pool = TrackingPool()

    # We need two different clients: one for GET (policy URL), one for POST (Ollama).
    # Because both use httpx.AsyncClient, we differentiate by call order.
    call_count = 0

    def client_factory(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        # First client instantiation: policy URL fetch (GET)
        ctx.get = AsyncMock(return_value=fake_http_response)
        # Second client instantiation: Ollama call (POST)
        ctx.post = AsyncMock(return_value=ollama_resp)
        return ctx

    with patch("consentflow.policy_auditor.httpx.AsyncClient", side_effect=client_factory):
        req = PolicyScanRequest(
            integration_name="Test Plugin",
            policy_url="https://example.com/privacy",
        )
        result = await auditor.scan(req, tracking_pool, fake_redis)

    assert result["overall_risk_level"] == "critical"
    assert len(result["findings"]) == 2
    assert result["findings"][0]["severity"] == "critical"
    assert result["findings"][1]["severity"] == "medium"
    assert result["integration_name"] == "Test Plugin"
    assert result["policy_url"] == "https://example.com/privacy"
    assert isinstance(result["scan_id"], uuid.UUID)
    assert isinstance(result["scanned_at"], datetime)
    assert result["findings_count"] == 2

    assert len(execute_calls) == 2, (
        f"Expected 2 DB execute() calls (policy_scans + audit_log), got {len(execute_calls)}"
    )
    assert any("policy_scans" in sql for sql in execute_calls)
    assert any("audit_log" in sql for sql in execute_calls)


# ── Test 2: Full scan — paste-text mode ───────────────────────────────────────


@pytest.mark.asyncio
async def test_full_scan_flow_paste_mode(fake_pool, fake_redis):
    """
    End-to-end scan in paste-text (no URL fetch) mode.

    Mocks: Ollama → 0 findings, overall_risk_level "low"
    Assertions:
    - result["overall_risk_level"] == "low"
    - result["findings"] == []
    - result["policy_url"] is None
    """
    auditor = _make_auditor(fake_pool, fake_redis)

    ollama_resp = _make_ollama_response(
        [],
        "No red flags detected. The policy appears GDPR- and CCPA-compliant.",
        "low",
    )

    get_mock = AsyncMock()

    def client_factory(*args, **kwargs):
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.get = get_mock
        ctx.post = AsyncMock(return_value=ollama_resp)
        return ctx

    with patch("consentflow.policy_auditor.httpx.AsyncClient", side_effect=client_factory):
        req = PolicyScanRequest(
            integration_name="Clean Plugin",
            policy_text=(
                "We collect only the minimum data necessary to provide our service. "
                "You may request deletion of your data at any time. "
                "We do not share data with third parties."
            ),
        )
        result = await auditor.scan(req, fake_pool, fake_redis)

    get_mock.assert_not_called()

    assert result["overall_risk_level"] == "low"
    assert result["findings"] == []
    assert result["findings_count"] == 0
    assert result["policy_url"] is None
    assert result["integration_name"] == "Clean Plugin"


# ── Test 3: POST /policy/scan API endpoint → 201 + scan_id ───────────────────


@pytest.mark.asyncio
async def test_api_endpoint_post_scan(fake_pool, fake_redis):
    """
    FastAPI endpoint smoke test: POST /policy/scan → 201.

    PolicyAuditor.scan is fully mocked so no real LLM, HTTP, or DB call is made.
    The Ollama reachability check (/api/tags) is also mocked to succeed.
    """
    scan_id = uuid.uuid4()
    scanned_at = datetime.now(tz=timezone.utc)

    mock_result = {
        "scan_id": scan_id,
        "integration_name": "Endpoint Test Plugin",
        "overall_risk_level": "high",
        "findings": [
            {
                "id": "finding_1",
                "severity": "high",
                "category": "Data Retention After Deletion Request",
                "clause_excerpt": "We retain all data for 10 years regardless of opt-out.",
                "explanation": "Post-revocation indefinite retention violates GDPR Art. 17.",
                "article_reference": "GDPR Article 17",
            }
        ],
        "findings_count": 1,
        "raw_summary": "One high-risk retention clause detected.",
        "scanned_at": scanned_at,
        "policy_url": None,
    }

    from consentflow.app.main import app

    app.state.db_pool = fake_pool
    app.state.redis_client = fake_redis

    # Mock the reachability GET and the scan invocation
    tags_resp = MagicMock()
    tags_resp.status_code = 200

    with (
        patch(
            "consentflow.app.routers.policy.PolicyAuditor.scan",
            new=AsyncMock(return_value=mock_result),
        ),
        patch(
            "consentflow.app.routers.policy.httpx.AsyncClient"
        ) as MockRouterClient,
    ):
        mock_router_ctx = AsyncMock()
        mock_router_ctx.__aenter__ = AsyncMock(return_value=mock_router_ctx)
        mock_router_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_router_ctx.get = AsyncMock(return_value=tags_resp)
        MockRouterClient.return_value = mock_router_ctx

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/policy/scan",
                json={
                    "integration_name": "Endpoint Test Plugin",
                    "policy_text": "We retain all data for 10 years regardless of any opt-out request.",
                },
            )

    assert response.status_code == 201, response.text

    body = response.json()
    assert "scan_id" in body
    assert uuid.UUID(body["scan_id"])
    assert body["overall_risk_level"] == "high"
    assert body["findings_count"] == 1
    assert body["integration_name"] == "Endpoint Test Plugin"


# ── Test 4: GET /policy/scans → 200 list of 3 items ──────────────────────────


@pytest.mark.asyncio
async def test_api_endpoint_get_scans(fake_pool, fake_redis):
    """GET /policy/scans → HTTP 200 with a list of 3 items."""
    now = datetime.now(tz=timezone.utc)
    scan_rows = [
        {
            "scan_id": uuid.uuid4(),
            "integration_name": f"Plugin {i}",
            "overall_risk_level": ("low", "medium", "critical")[i],
            "findings_count": i + 1,
            "scanned_at": now,
        }
        for i in range(3)
    ]

    class FakeRow(dict):
        def __getitem__(self, key):
            return super().__getitem__(key)

    fake_rows = [FakeRow(r) for r in scan_rows]

    class ScanListConnection:
        async def fetch(self, *args, **kwargs):
            return fake_rows

        async def fetchrow(self, *args, **kwargs):
            return None

        async def execute(self, *args, **kwargs):
            return None

        async def fetchval(self, *args, **kwargs):
            return len(fake_rows)

    class ScanListPool:
        def acquire(self):
            return self

        async def __aenter__(self):
            return ScanListConnection()

        async def __aexit__(self, *args):
            pass

    from consentflow.app.main import app

    app.state.db_pool = ScanListPool()
    app.state.redis_client = fake_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/policy/scans")

    assert response.status_code == 200, response.text

    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 3

    for item in body:
        assert "scan_id" in item
        assert "integration_name" in item
        assert "overall_risk_level" in item
        assert "findings_count" in item
        assert "scanned_at" in item


# ── Test 5: GET /policy/scans/{id} → 200 single result ───────────────────────


@pytest.mark.asyncio
async def test_api_endpoint_get_scan_by_id(fake_pool, fake_redis):
    """GET /policy/scans/{scan_id} → 200 with a full PolicyScanResult."""
    scan_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)

    class FakeSingleRow(dict):
        def __getitem__(self, key):
            return super().__getitem__(key)

    fake_row = FakeSingleRow(
        {
            "scan_id": scan_id,
            "integration_name": "Detail Plugin",
            "overall_risk_level": "medium",
            "findings": json.dumps([]),
            "findings_count": 0,
            "raw_summary": "No issues found.",
            "scanned_at": now,
            "policy_url": None,
        }
    )

    class SingleRowConnection:
        async def fetchrow(self, *args, **kwargs):
            return fake_row

        async def fetch(self, *args, **kwargs):
            return []

        async def execute(self, *args, **kwargs):
            return None

        async def fetchval(self, *args, **kwargs):
            return 1

    class SingleRowPool:
        def acquire(self):
            return self

        async def __aenter__(self):
            return SingleRowConnection()

        async def __aexit__(self, *args):
            pass

    from consentflow.app.main import app

    app.state.db_pool = SingleRowPool()
    app.state.redis_client = fake_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(f"/policy/scans/{scan_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall_risk_level"] == "medium"
    assert body["integration_name"] == "Detail Plugin"


# ── Test 6: GET /policy/scans/{id} → 404 ─────────────────────────────────────


@pytest.mark.asyncio
async def test_api_endpoint_get_scan_by_id_not_found(fake_pool, fake_redis):
    """GET /policy/scans/{scan_id} with unknown ID → 404."""

    class NotFoundConnection:
        async def fetchrow(self, *args, **kwargs):
            return None

        async def fetch(self, *args, **kwargs):
            return []

        async def execute(self, *args, **kwargs):
            return None

        async def fetchval(self, *args, **kwargs):
            return 0

    class NotFoundPool:
        def acquire(self):
            return self

        async def __aenter__(self):
            return NotFoundConnection()

        async def __aexit__(self, *args):
            pass

    from consentflow.app.main import app

    app.state.db_pool = NotFoundPool()
    app.state.redis_client = fake_redis

    missing_id = uuid.uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(f"/policy/scans/{missing_id}")

    assert response.status_code == 404, response.text


# ── Test 7: POST /policy/scan → 503 when Ollama unreachable ──────────────────


@pytest.mark.asyncio
async def test_scan_returns_503_when_ollama_unreachable(fake_pool, fake_redis):
    """
    When the GET /api/tags reachability check raises ConnectError → 503.
    """
    from consentflow.app.main import app

    app.state.db_pool = fake_pool
    app.state.redis_client = fake_redis

    fake_request_obj = httpx.Request("GET", "http://localhost:11434/api/tags")

    with patch(
        "consentflow.app.routers.policy.httpx.AsyncClient"
    ) as MockRouterClient:
        mock_router_ctx = AsyncMock()
        mock_router_ctx.__aenter__ = AsyncMock(return_value=mock_router_ctx)
        mock_router_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_router_ctx.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused", request=fake_request_obj)
        )
        MockRouterClient.return_value = mock_router_ctx

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/policy/scan",
                json={
                    "integration_name": "Smoke Test",
                    "policy_text": "Some policy text.",
                },
            )

    assert response.status_code == 503, response.text
    assert "Ollama" in response.json()["detail"]


# ── Test 8: POST /policy/scan → 422 when policy URL fetch fails ───────────────


@pytest.mark.asyncio
async def test_scan_returns_422_when_policy_url_fetch_fails(fake_pool, fake_redis):
    """
    When the policy_url cannot be fetched → 422 Unprocessable Entity.
    """
    from consentflow.app.main import app

    app.state.db_pool = fake_pool
    app.state.redis_client = fake_redis

    tags_resp = MagicMock()
    tags_resp.status_code = 200

    with (
        patch(
            "consentflow.app.routers.policy.httpx.AsyncClient"
        ) as MockRouterClient,
        patch(
            "consentflow.app.routers.policy.PolicyAuditor.scan",
            new=AsyncMock(side_effect=PolicyFetchError("HTTP 404 fetching policy")),
        ),
    ):
        mock_router_ctx = AsyncMock()
        mock_router_ctx.__aenter__ = AsyncMock(return_value=mock_router_ctx)
        mock_router_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_router_ctx.get = AsyncMock(return_value=tags_resp)
        MockRouterClient.return_value = mock_router_ctx

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/policy/scan",
                json={
                    "integration_name": "BadURL Plugin",
                    "policy_url": "https://nonexistent.example.com/policy",
                },
            )

    assert response.status_code == 422, response.text


# ── Test 9: POST /policy/scan → 502 when LLM call fails ──────────────────────


@pytest.mark.asyncio
async def test_scan_returns_502_when_llm_fails(fake_pool, fake_redis):
    """
    When PolicyAuditor.scan raises PolicyAnalysisError → 502 Bad Gateway.
    """
    from consentflow.app.main import app
    from consentflow.policy_auditor import PolicyAnalysisError

    app.state.db_pool = fake_pool
    app.state.redis_client = fake_redis

    tags_resp = MagicMock()
    tags_resp.status_code = 200

    with (
        patch(
            "consentflow.app.routers.policy.httpx.AsyncClient"
        ) as MockRouterClient,
        patch(
            "consentflow.app.routers.policy.PolicyAuditor.scan",
            new=AsyncMock(side_effect=PolicyAnalysisError("LLM call failed")),
        ),
    ):
        mock_router_ctx = AsyncMock()
        mock_router_ctx.__aenter__ = AsyncMock(return_value=mock_router_ctx)
        mock_router_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_router_ctx.get = AsyncMock(return_value=tags_resp)
        MockRouterClient.return_value = mock_router_ctx

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/policy/scan",
                json={
                    "integration_name": "Broken LLM Plugin",
                    "policy_text": "Some policy text.",
                },
            )

    assert response.status_code == 502, response.text


# ── Test 10: Risk-level recomputation — highest severity wins ─────────────────


@pytest.mark.asyncio
async def test_risk_level_propagation(fake_pool, fake_redis):
    """
    When the LLM returns findings with mixed severities but an incorrect
    overall_risk_level, the auditor overrides it with the computed max.
    """
    auditor = _make_auditor(fake_pool, fake_redis)

    mixed_findings = [
        {
            "id": "f1", "severity": "low", "category": "Minor Issue",
            "clause_excerpt": "We use analytics cookies.", "explanation": "Low impact.",
            "article_reference": "",
        },
        {
            "id": "f2", "severity": "critical", "category": "Training on Inputs",
            "clause_excerpt": "We may train AI on your inputs.",
            "explanation": "Critical training without consent.",
            "article_reference": "GDPR Article 6(1)",
        },
    ]

    # LLM mis-reports risk as "low" despite a critical finding
    ollama_resp = _make_ollama_response(
        mixed_findings, "Mixed findings.", "low"   # intentionally wrong
    )

    def client_factory(*args, **kwargs):
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(return_value=ollama_resp)
        return ctx

    with patch("consentflow.policy_auditor.httpx.AsyncClient", side_effect=client_factory):
        findings, summary, risk_level = await auditor.analyze_policy(
            "We may train AI on your inputs.", "MixedPlugin"
        )

    # The auditor must override "low" → "critical"
    assert risk_level == "critical", (
        f"Expected 'critical' after recomputation, got '{risk_level}'"
    )
    assert len(findings) == 2
