"""
routers/policy.py — Gate 05: Policy Auditor REST endpoints.

Endpoints
---------
POST /policy/scan              — Analyse a privacy policy and store results.
GET  /policy/scans             — List previous scan results (paginated).
GET  /policy/scans/{scan_id}   — Retrieve a single scan result by UUID.
"""
from __future__ import annotations

import json
import logging
from typing import Any, List, Optional
from uuid import UUID

import asyncpg
import httpx
from fastapi import APIRouter, HTTPException, Query, Request, status

from consentflow.app.config import settings
from consentflow.app.models import (
    PolicyFinding,
    PolicyScanListItem,
    PolicyScanRequest,
    PolicyScanResult,
)
from consentflow.policy_auditor import PolicyAuditor, PolicyAnalysisError, PolicyFetchError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/policy", tags=["policy-auditor"])


# ── Dependency helpers ─────────────────────────────────────────────────────────


def _get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool  # type: ignore[no-any-return]


def _get_redis(request: Request):
    return request.app.state.redis_client


# ── Helpers ────────────────────────────────────────────────────────────────────


def _row_to_findings(raw_findings) -> List[PolicyFinding]:
    """
    Deserialise the ``findings`` JSONB column to a list of ``PolicyFinding``.

    asyncpg may return JSONB as a ``str`` or already as a Python ``list``
    depending on the codec configuration, so we handle both.
    """
    if isinstance(raw_findings, str):
        try:
            raw_findings = json.loads(raw_findings)
        except (json.JSONDecodeError, TypeError):
            raw_findings = []

    if not isinstance(raw_findings, list):
        raw_findings = []

    findings: List[PolicyFinding] = []
    for item in raw_findings:
        try:
            findings.append(PolicyFinding(**item))
        except Exception:  # noqa: BLE001
            logger.warning("Skipping malformed finding record: %r", item)
    return findings


# ── POST /policy/scan ──────────────────────────────────────────────────────────


@router.post(
    "/scan",
    response_model=PolicyScanResult,
    status_code=status.HTTP_201_CREATED,
    summary="Scan a privacy policy",
    description=(
        "Fetch and analyse an AI plugin's privacy policy or Terms of Service. "
        "Detects clauses that could bypass or override a user's consent "
        "revocation under GDPR and CCPA. "
        "Supply at least one of ``policy_url`` (publicly reachable) or "
        "``policy_text`` (raw document)."
    ),
    responses={
        201: {"description": "Scan completed and persisted"},
        422: {"description": "Could not fetch the policy URL"},
        502: {"description": "LLM analysis service unavailable"},
    },
)
async def post_policy_scan(
    body: PolicyScanRequest,
    request: Request,
) -> PolicyScanResult:
    """Analyse a privacy policy and return a structured risk report."""
    db_pool = _get_pool(request)
    redis_client = _get_redis(request)

    # ── LLM reachability handled by LangChain fallbacks ────────────────────────

    auditor = PolicyAuditor(
        db_pool=db_pool,
        redis_client=redis_client,
    )

    try:
        result_dict = await auditor.scan(body)
    except PolicyFetchError as exc:
        logger.warning("PolicyAuditor fetch error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not fetch policy URL: {exc}",
        ) from exc
    except (PolicyAnalysisError, ValueError) as exc:
        logger.error("PolicyAuditor analysis error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM analysis failed: {exc}",
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("PolicyAuditor Ollama HTTP error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM service error: {exc}",
        ) from exc
    finally:
        await auditor._close()

    # Build typed Pydantic model from the returned dict
    findings = [PolicyFinding(**f) for f in result_dict["findings"]]

    return PolicyScanResult(
        scan_id=result_dict["scan_id"],
        integration_name=result_dict["integration_name"],
        overall_risk_level=result_dict["overall_risk_level"],
        findings=findings,
        findings_count=result_dict["findings_count"],
        raw_summary=result_dict["raw_summary"],
        scanned_at=result_dict["scanned_at"],
        policy_url=result_dict["policy_url"],
    )


# ── GET /policy/scans ──────────────────────────────────────────────────────────


@router.get(
    "/scans",
    response_model=List[PolicyScanListItem],
    status_code=status.HTTP_200_OK,
    summary="List policy scans",
    description=(
        "Return a paginated, newest-first list of all policy audit scans. "
        "Optionally filter by ``risk_level`` (low | medium | high | critical)."
    ),
    responses={
        200: {"description": "List of scan summaries"},
        500: {"description": "Database error"},
    },
)
async def list_policy_scans(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100, description="Max rows to return"),
    offset: int = Query(default=0, ge=0, description="Rows to skip (pagination)"),
    risk_level: Optional[str] = Query(
        default=None,
        description="Filter by overall_risk_level (low | medium | high | critical)",
    ),
) -> List[PolicyScanListItem]:
    """Return a paginated list of policy scan summaries."""
    pool = _get_pool(request)

    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if risk_level is not None:
        conditions.append(f"overall_risk_level = ${idx}")
        params.append(risk_level.lower())
        idx += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sql = f"""
        SELECT id AS scan_id,
               integration_name,
               overall_risk_level,
               findings_count,
               scanned_at
          FROM policy_scans
         {where_clause}
         ORDER BY scanned_at DESC
         LIMIT ${idx} OFFSET ${idx + 1}
    """
    params.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [
        PolicyScanListItem(
            scan_id=UUID(str(row["scan_id"])),
            integration_name=row["integration_name"],
            overall_risk_level=row["overall_risk_level"],
            findings_count=row["findings_count"],
            scanned_at=row["scanned_at"],
        )
        for row in rows
    ]


# ── GET /policy/scans/{scan_id} ────────────────────────────────────────────────


@router.get(
    "/scans/{scan_id}",
    response_model=PolicyScanResult,
    status_code=status.HTTP_200_OK,
    summary="Get a policy scan by ID",
    description="Retrieve the full result of a specific policy audit scan.",
    responses={
        200: {"description": "Scan result found"},
        404: {"description": "Scan not found"},
        500: {"description": "Database error"},
    },
)
async def get_policy_scan(
    scan_id: UUID,
    request: Request,
) -> PolicyScanResult:
    """Retrieve a single policy scan result by its UUID."""
    pool = _get_pool(request)

    sql = """
        SELECT id AS scan_id,
               integration_name,
               overall_risk_level,
               findings,
               findings_count,
               raw_summary,
               scanned_at,
               policy_url
          FROM policy_scans
         WHERE id = $1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, scan_id)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy scan {scan_id} not found.",
        )

    findings = _row_to_findings(row["findings"])

    return PolicyScanResult(
        scan_id=UUID(str(row["scan_id"])),
        integration_name=row["integration_name"],
        overall_risk_level=row["overall_risk_level"],
        findings=findings,
        findings_count=row["findings_count"],
        raw_summary=row["raw_summary"] or "",
        scanned_at=row["scanned_at"],
        policy_url=row["policy_url"],
    )
