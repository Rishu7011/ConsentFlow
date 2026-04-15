from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl, model_validator


class ConsentStatus(str, Enum):
    granted = "granted"
    revoked = "revoked"


# ── Request models ─────────────────────────────────────────────────────────────


class ConsentUpsertRequest(BaseModel):
    """Payload for POST /consent — grant or revoke a consent record."""

    user_id: UUID = Field(..., description="UUID of the user")
    data_type: str = Field(..., min_length=1, max_length=128, description="Category of data (e.g. 'pii', 'usage')")
    purpose: str = Field(..., min_length=1, max_length=256, description="Processing purpose (e.g. 'analytics')")
    status: ConsentStatus = Field(..., description="'granted' or 'revoked'")


class ConsentRevokeRequest(BaseModel):
    """Payload for POST /consent/revoke."""

    user_id: UUID = Field(..., description="UUID of the user")
    purpose: str = Field(..., min_length=1, max_length=256, description="Purpose to revoke")


class UserCreateRequest(BaseModel):
    """Payload for creating a new user (utility endpoint)."""

    email: EmailStr = Field(..., description="User's e-mail address")


# ── Response models ────────────────────────────────────────────────────────────


class ConsentRecord(BaseModel):
    """Full consent record returned from the DB."""

    id: UUID
    user_id: UUID
    data_type: str
    purpose: str
    status: ConsentStatus
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConsentStatusResponse(BaseModel):
    """Lightweight status lookup response for GET /consent/{user_id}/{purpose}."""

    user_id: UUID
    purpose: str
    status: ConsentStatus
    updated_at: datetime
    cached: bool = Field(default=False, description="True when the result was served from Redis")


class UserRecord(BaseModel):
    id: UUID
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListRecord(BaseModel):
    """Enriched user record returned from GET /users, includes consent summary."""

    id: UUID
    email: str
    created_at: datetime
    consents: int = Field(default=0, description="Total number of consent records for this user")
    status: str = Field(
        default="pending",
        description="Derived status: 'active' if any granted consent, 'revoked' if all revoked, 'pending' if none",
    )

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str = "ok"
    postgres: str
    redis: str
    kafka: Optional[str] = None
    otel: Optional[str] = None


# ── Step 7: Audit log models ───────────────────────────────────────────────────


class AuditLogEntry(BaseModel):
    """A single row from the audit_log table."""

    id: UUID
    event_time: datetime
    user_id: str
    gate_name: str
    action_taken: str
    consent_status: str
    purpose: str | None = None
    metadata: dict | None = None
    trace_id: str | None = None

    model_config = {"from_attributes": True}


class AuditTrailResponse(BaseModel):
    """Response envelope for GET /audit/trail."""

    entries: list[AuditLogEntry]
    total: int


# ── Gate 05: Policy Auditor models ────────────────────────────────────────────


class PolicyFinding(BaseModel):
    """A single red-flag finding extracted from a policy document."""

    id: str = Field(..., description="Unique identifier for this finding within the scan")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="How severe this clause is from a consent perspective"
    )
    category: str = Field(
        ..., description="Finding category, e.g. 'data_retention', 'third_party_sharing'"
    )
    clause_excerpt: Optional[str] = Field(
        default=None, description="Verbatim excerpt of the offending clause from the policy text"
    )
    explanation: Optional[str] = Field(
        default=None, description="Plain-English explanation of why this clause is a red flag"
    )
    article_reference: Optional[str] = Field(
        default=None,
        description="GDPR / CCPA article or regulation reference (e.g. 'GDPR Art. 17')",
    )


class PolicyScanRequest(BaseModel):
    """Payload for POST /policy-auditor/scan — supply a URL, raw text, or both."""

    integration_name: str = Field(
        ..., min_length=1, max_length=256,
        description="Human-readable name of the plugin or integration to scan",
    )
    policy_url: Optional[HttpUrl] = Field(
        default=None,
        description="Publicly reachable URL of the privacy policy or ToS document",
    )
    policy_text: Optional[str] = Field(
        default=None,
        description="Raw policy text to scan (used when the URL is not publicly accessible)",
    )

    @model_validator(mode="after")
    def _require_url_or_text(self) -> "PolicyScanRequest":
        if self.policy_url is None and (self.policy_text is None or self.policy_text.strip() == ""):
            raise ValueError(
                "At least one of 'policy_url' or 'policy_text' must be provided."
            )
        return self


class PolicyScanResult(BaseModel):
    """Full scan result returned from POST /policy-auditor/scan."""

    scan_id: UUID = Field(..., description="UUID of the persisted policy_scans row")
    integration_name: str
    overall_risk_level: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Aggregate risk verdict for the scanned document"
    )
    findings: List[PolicyFinding] = Field(
        default_factory=list, description="All red-flag findings detected in the document"
    )
    findings_count: int = Field(..., description="Total number of findings (matches len(findings))")
    raw_summary: str = Field(..., description="LLM-generated plain-English summary of the scan")
    scanned_at: datetime = Field(..., description="Timestamp when the scan was completed")
    policy_url: Optional[str] = Field(
        default=None, description="Source URL that was scanned, if one was supplied"
    )

    model_config = {"from_attributes": True}


class PolicyScanListItem(BaseModel):
    """Lightweight row returned from GET /policy-auditor/scans (list view)."""

    scan_id: UUID
    integration_name: str
    overall_risk_level: str
    findings_count: int
    scanned_at: datetime

    model_config = {"from_attributes": True}
