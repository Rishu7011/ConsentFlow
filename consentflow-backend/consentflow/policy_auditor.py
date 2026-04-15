"""
consentflow/policy_auditor.py — Gate 05: Policy Auditor

Fetches and analyses AI plugin privacy policies and Terms of Service using a
local Ollama LLM via its OpenAI-compatible endpoint.  Detects clauses that
could bypass or override a user's consent revocation under GDPR and CCPA.

Public API
----------
    auditor = PolicyAuditor(db_pool, redis_client)
    result  = await auditor.scan(request, db_pool, redis_client)

    # Thin functional helpers (used directly in tests / router):
    result = await analyze_policy(policy_text, integration_name, settings)
    text   = await fetch_policy_text(url, settings)

Exceptions
----------
    httpx.HTTPError  — Ollama unreachable or policy URL fetch failure.
                       Router catches these and maps them to 502 / 422.
    ValueError       — LLM returned content that cannot be parsed as JSON.
                       Router catches this and returns 502.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Maximum characters sent to the LLM (context safety guard).
_MAX_POLICY_CHARS: int = 12_000

# Severity ordering for recomputing overall_risk_level.
_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_VALID_SEVERITIES = frozenset(_SEVERITY_ORDER)

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT: str = """
You are a privacy law expert analysing AI plugin Terms of Service and Privacy Policies on behalf of users who want to understand if the integration respects their consent preferences under GDPR and CCPA.

Identify clauses that could bypass, override, or undermine a user's consent revocation. Check exactly these 7 categories:
1. Training on Inputs
2. Broad Data Sharing
3. Irrevocable License Grant
4. Opt-Out Only (no opt-in)
5. Retroactive Policy Changes
6. Data Retention After Deletion Request
7. Cross-Context Behavioral Tracking

Return ONLY a raw JSON object — no markdown fences, no commentary. Use this exact schema:
{{
  "findings": [
    {{
      "id": "finding_1",
      "severity": "low|medium|high|critical",
      "category": "<one of the 7 categories above>",
      "clause_excerpt": "<verbatim excerpt, max 300 chars>",
      "explanation": "<plain English explanation of the risk>",
      "article_reference": "<e.g. GDPR Article 7(3) or CCPA 1798.120>"
    }}
  ],
  "overall_risk_level": "low|medium|high|critical",
  "raw_summary": "<2-3 sentence executive summary>"
}}

Rules:
- overall_risk_level must equal the highest severity across all findings, or "low" if findings is empty.
- If no red flags are found, return findings as an empty array and overall_risk_level as "low".
""".strip()


# ── Custom exceptions ──────────────────────────────────────────────────────────


class PolicyFetchError(RuntimeError):
    """Raised when the policy document cannot be retrieved or decoded."""


class PolicyAnalysisError(RuntimeError):
    """Raised when the Ollama API call fails at the network/auth level."""


# ── HTML text extraction ───────────────────────────────────────────────────────


class _TextExtractor(HTMLParser):
    """Minimal HTMLParser subclass that collects visible text nodes."""

    _SKIP_TAGS = frozenset(
        {"script", "style", "noscript", "head", "meta", "link", "svg", "img"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._depth: int = 0
        self._skip_tag: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
        if self._skip_tag or tag in self._SKIP_TAGS:
            if not self._skip_tag:
                self._skip_tag = tag
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if self._skip_tag:
            self._depth -= 1
            if self._depth == 0:
                self._skip_tag = None

    def handle_data(self, data: str) -> None:
        if not self._skip_tag:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    @property
    def text(self) -> str:
        return " ".join(self._parts)


def _strip_html(raw: str) -> str:
    """Return plain text extracted from an HTML document."""
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        return parser.text
    except Exception:  # noqa: BLE001
        logger.warning("HTML parser raised an exception; returning raw text as fallback.")
        return raw


def _strip_markdown_fences(text: str) -> str:
    """Remove accidental markdown code fences that some models add despite json_object mode."""
    stripped = text.strip()
    # Match ```json ... ``` or ``` ... ```
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _validate_severity(value: str, context: str = "") -> str:
    """Return *value* if it is a known severity, else warn and return 'low'."""
    if value in _VALID_SEVERITIES:
        return value
    logger.warning(
        "Unknown severity %r%s; defaulting to 'low'.",
        value,
        f" ({context})" if context else "",
    )
    return "low"


def _compute_max_severity(findings: list[dict]) -> str:
    """Return the highest severity present in *findings*, or 'low' if empty."""
    max_rank = 0
    max_sev = "low"
    for f in findings:
        sev = f.get("severity", "low")
        if sev not in _VALID_SEVERITIES:
            sev = "low"
        rank = _SEVERITY_ORDER[sev]
        if rank > max_rank:
            max_rank = rank
            max_sev = sev
    return max_sev


# ── Functional helpers (thin wrappers; used by the class and the tests) ────────


async def fetch_policy_text(url: str, settings) -> str:
    """
    Fetch a privacy policy document from *url* and return plain text.

    Raises
    ------
    httpx.HTTPError
        On any network error or non-2xx status.
    """
    logger.info("PolicyAuditor: fetching policy from %s", url)
    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    try:
        raw_text: str = response.text
    except Exception as exc:  # noqa: BLE001
        raise httpx.RequestError(
            f"Could not decode response body from {url}: {exc}"
        ) from exc

    content_type = response.headers.get("content-type", "")
    if "html" in content_type:
        plain = _strip_html(raw_text)
    else:
        plain = raw_text

    plain = " ".join(plain.split())

    if len(plain) > _MAX_POLICY_CHARS:
        logger.debug(
            "PolicyAuditor: truncating policy text from %d to %d chars",
            len(plain),
            _MAX_POLICY_CHARS,
        )
        plain = plain[:_MAX_POLICY_CHARS] + " [... document truncated for analysis ...]"

    if not plain.strip():
        raise httpx.RequestError(
            f"Fetched document from {url} yielded no extractable text."
        )

    return plain


async def analyze_policy(
    policy_text: str,
    integration_name: str,
    settings,
) -> "PolicyScanResult":
    """
    Send policy text to the local Ollama LLM and return a PolicyScanResult-like dict.

    Parameters
    ----------
    policy_text:       Raw policy text (will be truncated to _MAX_POLICY_CHARS).
    integration_name:  Human-readable name of the third-party integration.
    settings:          App Settings instance (provides ollama_base_url / ollama_model).

    Returns
    -------
    Tuple[list[dict], str, str]
        (findings_dicts, raw_summary, overall_risk_level)

    Raises
    ------
    httpx.HTTPError  — Ollama unreachable or returned a non-2xx status.
    ValueError       — LLM response could not be parsed as JSON.
    """
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_mistralai import ChatMistralAI
    from langchain_ollama import ChatOllama

    # Truncate before sending
    text = policy_text
    if len(text) > _MAX_POLICY_CHARS:
        text = text[:_MAX_POLICY_CHARS] + " [... document truncated for analysis ...]"

    user_message = f"Integration name: {integration_name}\n\nPolicy text:\n{text}"

    logger.info(
        "PolicyAuditor: calling LLM chain (Mistral->Gemini->Ollama) integration=%r text_len=%d",
        integration_name,
        len(text),
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{user_message}")
    ])

    # 1. Setup Ollama Fallback Model
    ollama_model = ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url.rstrip("/"),
        temperature=0.1,
        format="json",
    )

    # 2. Setup Mistral Secondary Fallback Model
    mistral_chain = ollama_model
    if settings.mistral_api_key:
        mistral_model = ChatMistralAI(
            model=settings.mistral_model,
            mistral_api_key=settings.mistral_api_key,
            temperature=0.1,
        )
        mistral_chain = mistral_model.with_fallbacks([ollama_model])

    # 3. Setup Gemini Primary Model
    model_chain = mistral_chain
    if settings.gemini_api_key:
        gemini_model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.gemini_api_key,
            temperature=0.1,
        )
        model_chain = gemini_model.with_fallbacks([mistral_chain])

    chain = prompt_template | model_chain

    try:
        response = await chain.ainvoke({"user_message": user_message})
        raw_content = response.content
    except Exception as exc:
        raise PolicyAnalysisError(f"All LLM fallbacks failed: {exc}") from exc

    logger.debug(
        "PolicyAuditor: raw LLM response (first 500 chars): %s",
        raw_content[:500],
    )

    # Strip any accidental markdown fences
    cleaned = _strip_markdown_fences(raw_content)

    try:
        parsed: dict = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"Ollama returned non-JSON content for integration={integration_name!r}: {exc}"
        ) from exc

    findings: list = parsed.get("findings", [])
    raw_summary: str = parsed.get("raw_summary", parsed.get("summary", ""))
    risk_level: str = parsed.get("overall_risk_level", "low")

    # Validate and normalise finding severities
    for finding in findings:
        finding["severity"] = _validate_severity(
            finding.get("severity", "low"),
            context=f"finding id={finding.get('id', '?')}",
        )

    # Validate LLM-reported overall_risk_level
    risk_level = _validate_severity(risk_level, context="overall_risk_level")

    # Safety net: recompute from findings and override if LLM under-reported
    computed_max = _compute_max_severity(findings)
    if _SEVERITY_ORDER[computed_max] > _SEVERITY_ORDER[risk_level]:
        logger.warning(
            "PolicyAuditor: LLM reported overall_risk_level=%r but computed max is %r; overriding.",
            risk_level,
            computed_max,
        )
        risk_level = computed_max

    return findings, raw_summary, risk_level


# ── Main auditor class ─────────────────────────────────────────────────────────


class PolicyAuditor:
    """
    Gate 05 — Policy Auditor.

    Parameters
    ----------
    db_pool:      asyncpg connection pool (injected, not imported).
    redis_client: aioredis / redis-py async client (reserved for future caching).
    """

    def __init__(
        self,
        db_pool,
        redis_client,
    ) -> None:
        self._db_pool = db_pool
        self._redis = redis_client

    # Kept for router compatibility — router calls auditor._close() in finally block.
    async def _close(self) -> None:
        """No-op: no persistent connections to release."""

    async def __aenter__(self) -> "PolicyAuditor":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._close()

    # ── Step 1: Fetch ──────────────────────────────────────────────────────────

    async def fetch_policy_text(self, url: str, settings=None) -> str:
        """
        Fetch a privacy policy document from *url* and return plain text.

        Raises
        ------
        PolicyFetchError
            On any network error, non-2xx status, or decoding failure.
        """
        from consentflow.app.config import settings as _settings
        _s = settings or _settings
        try:
            return await fetch_policy_text(url, _s)
        except httpx.HTTPStatusError as exc:
            raise PolicyFetchError(
                f"HTTP {exc.response.status_code} fetching policy from {url}"
            ) from exc
        except httpx.RequestError as exc:
            raise PolicyFetchError(
                f"Network error fetching policy from {url}: {exc}"
            ) from exc

    # ── Step 2: Analyse ────────────────────────────────────────────────────────

    async def analyze_policy(
        self,
        text: str,
        integration_name: str,
        settings=None,
    ) -> Tuple[List[dict], str, str]:
        """
        Send policy text to Ollama and return parsed findings.

        Returns
        -------
        (findings_dicts, raw_summary, overall_risk_level)
        """
        from consentflow.app.config import settings as _settings
        _s = settings or _settings
        return await analyze_policy(text, integration_name, _s)

    # ── Step 3: Scan (orchestrator) ────────────────────────────────────────────

    async def scan(
        self,
        request,   # PolicyScanRequest — not imported to keep this module self-contained
        settings=None,
    ):
        """
        Full scan pipeline:

        1. Resolve policy text (URL fetch or direct text).
        2. Compute SHA-256 hash for deduplication.
        3. Call Ollama LLM to analyse the text.
        4. Persist to ``policy_scans`` via asyncpg.
        5. Write an ``audit_log`` row for this gate action.
        6. Return a ``PolicyScanResult``-compatible dict.

        Returns
        -------
        dict
            Keys: scan_id, integration_name, overall_risk_level, findings,
                  findings_count, raw_summary, scanned_at, policy_url.
        """
        from consentflow.app.config import settings as _settings
        _s = settings or _settings

        # ── 1. Resolve text ───────────────────────────────────────────────────
        policy_url_str: Optional[str] = None

        if request.policy_url is not None:
            policy_url_str = str(request.policy_url)
            policy_text = await self.fetch_policy_text(policy_url_str, _s)
        elif request.policy_text:
            policy_text = request.policy_text[:_MAX_POLICY_CHARS]
        else:
            raise PolicyFetchError(
                "PolicyScanRequest must supply policy_url or policy_text."
            )

        # ── 2. Hash ───────────────────────────────────────────────────────────
        text_hash: str = hashlib.sha256(
            policy_text.encode("utf-8", errors="replace")
        ).hexdigest()

        # ── 3. Analyse ────────────────────────────────────────────────────────
        findings_dicts, raw_summary, overall_risk_level = await self.analyze_policy(
            policy_text, request.integration_name, _s
        )
        findings_count: int = len(findings_dicts)

        # ── 4. Persist policy_scans ───────────────────────────────────────────
        scan_id = uuid.uuid4()
        scanned_at = datetime.now(tz=timezone.utc)

        insert_scan_sql = """
            INSERT INTO policy_scans (
                id, scanned_at, integration_name, policy_url,
                policy_text_hash, overall_risk_level,
                findings_count, findings, raw_summary
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """

        async with self._db_pool.acquire() as conn:
            await conn.execute(
                insert_scan_sql,
                scan_id,
                scanned_at,
                request.integration_name,
                policy_url_str,
                text_hash,
                overall_risk_level,
                findings_count,
                json.dumps(findings_dicts),
                raw_summary,
            )

            # ── 5. Audit log row ──────────────────────────────────────────────
            audit_metadata = {
                "integration_name": request.integration_name,
                "overall_risk_level": overall_risk_level,
                "findings_count": findings_count,
                "policy_url": policy_url_str,
                "scan_id": str(scan_id),
            }

            insert_audit_sql = """
                INSERT INTO audit_log (
                    id, event_time, user_id, gate_name, action_taken,
                    consent_status, purpose, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """

            audit_id = uuid.uuid4()
            await conn.execute(
                insert_audit_sql,
                audit_id,
                scanned_at,
                "system",
                "policy_auditor",
                "scanned",
                "unknown",
                "policy_audit",
                json.dumps(audit_metadata),
            )

            logger.info(
                "PolicyAuditor: scan complete — integration=%r risk=%s findings=%d "
                "scan_id=%s audit_id=%s",
                request.integration_name,
                overall_risk_level,
                findings_count,
                scan_id,
                audit_id,
            )

        # ── 6. Return result dict ─────────────────────────────────────────────
        return {
            "scan_id": scan_id,
            "integration_name": request.integration_name,
            "overall_risk_level": overall_risk_level,
            "findings": findings_dicts,
            "findings_count": findings_count,
            "raw_summary": raw_summary,
            "scanned_at": scanned_at,
            "policy_url": policy_url_str,
        }
