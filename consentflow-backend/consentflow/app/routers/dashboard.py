from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

class DashboardStatsResponse(BaseModel):
    users: int
    granted: int
    blocked: int
    purposes: dict[str, int]
    checks_24h_total: int
    checks_24h_allowed: int
    checks_24h_blocked: int
    checks_sparkline: list[int]
    policy_scans_total: int = 0
    policy_scans_critical: int = 0

def _get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool

@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Dashboard Metrics",
)
async def get_dashboard_stats(
    pool: asyncpg.Pool = Depends(_get_pool),
) -> DashboardStatsResponse:
    users_sql = "SELECT COUNT(*) FROM users"
    granted_sql = "SELECT COUNT(*) FROM consent_records WHERE status = 'granted'"
    blocked_sql = "SELECT COUNT(*) FROM audit_log WHERE action_taken IN ('memory_blocked', 'BLOCKED')"
    
    purposes_sql = "SELECT purpose, COUNT(*) FROM consent_records WHERE status = 'granted' GROUP BY purpose"
    
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(hours=24)
    # Using inference gate specific checks
    checks_sql = "SELECT event_time, action_taken FROM audit_log WHERE event_time >= $1 AND gate_name = 'inference_gate'"

    # Gate 05 — Policy Auditor
    policy_scans_total_sql = "SELECT COUNT(*) FROM policy_scans"
    policy_scans_critical_sql = "SELECT COUNT(*) FROM policy_scans WHERE overall_risk_level = 'critical'"

    async with pool.acquire() as conn:
        users = await conn.fetchval(users_sql)
        granted = await conn.fetchval(granted_sql)
        blocked = await conn.fetchval(blocked_sql)
        
        purposes_rows = await conn.fetch(purposes_sql)
        checks_rows = await conn.fetch(checks_sql, twenty_four_hours_ago)

        try:
            policy_scans_total = await conn.fetchval(policy_scans_total_sql) or 0
            policy_scans_critical = await conn.fetchval(policy_scans_critical_sql) or 0
        except Exception:
            # Table may not exist yet in older deployments
            policy_scans_total = 0
            policy_scans_critical = 0

    purposes = {row["purpose"]: row["count"] for row in purposes_rows}
    
    checks_24h_total = len(checks_rows)
    checks_24h_allowed = sum(1 for row in checks_rows if row["action_taken"] == "ALLOWED")
    checks_24h_blocked = sum(1 for row in checks_rows if row["action_taken"] == "BLOCKED")
    
    # 24 buckets for sparkline
    sparkline = [0] * 24
    for row in checks_rows:
        # Calculate which hour bucket it falls into (0 is the oldest, 23 is the newest)
        diff = now - row["event_time"]
        bucket_idx = 23 - int(diff.total_seconds() // 3600)
        if 0 <= bucket_idx <= 23:
            sparkline[bucket_idx] += 1

    return DashboardStatsResponse(
        users=users or 0,
        granted=granted or 0,
        blocked=blocked or 0,
        purposes=purposes,
        checks_24h_total=checks_24h_total,
        checks_24h_allowed=checks_24h_allowed,
        checks_24h_blocked=checks_24h_blocked,
        checks_sparkline=sparkline,
        policy_scans_total=policy_scans_total,
        policy_scans_critical=policy_scans_critical,
    )
