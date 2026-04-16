"""
extension.py — FastAPI router for the ConsentFlow Privacy Shield browser extension.

Step 10 of the ConsentFlow Privacy Shield build.

PRIVACY CONTRACT:
  This router NEVER receives, logs, or stores real PII.
  It only processes entity-type placeholder tokens like "[PERSON_1]".

Endpoints:
  POST /api/v1/extension/anonymize       — swap placeholders for random dummies
  GET  /api/v1/extension/consent-profile — return the user's enabled PII types
"""
from __future__ import annotations

import logging
import random
import re
import string

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from consentflow.app.cache import get_consent_cache
from consentflow.app.models import ExtensionAnonymizePlaceholderRequest

logger = logging.getLogger(__name__)

# ─── Router ───────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/v1/extension", tags=["extension"])

# ─── CORS helper for chrome-extension:// origins ─────────────────────────────

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _cors(response: Response) -> None:
    """Add permissive CORS headers so the extension can reach this router."""
    for k, v in _CORS_HEADERS.items():
        response.headers[k] = v


# ─── Default profile ──────────────────────────────────────────────────────────

DEFAULT_PII_PROFILE: dict[str, bool] = {
    "PERSON": True,
    "PHONE_NUMBER": True,
    "EMAIL_ADDRESS": True,
    "IN_AADHAAR": True,
    "IN_PAN": True,
    "UPI_ID": True,
}

# ─── Dummy generator ──────────────────────────────────────────────────────────

_PERSON_NAMES = [
    "Alex Smith",
    "Jordan Lee",
    "Sam Taylor",
    "Morgan Davis",
    "Casey Brown",
    "Riley Wilson",
]


def _generate_dummy(entity_ref: str) -> str:
    """
    Extract entity type from a placeholder token (e.g. "[PERSON_1]" → "PERSON")
    and return a random, realistic-looking dummy value.

    The dummy is safe to pass back to the content script — it never contains
    real PII.
    """
    # Extract type + counter: "[PERSON_1]" → ("PERSON", "1")
    match = re.match(r"\[([A-Z_]+)_(\d+)\]", entity_ref)
    entity_type = match.group(1) if match else ""
    counter = match.group(2) if match else ""

    # Non-semantic redactions for all known types so the model cannot infer
    # what kind of PII was shared (e.g. a 10-digit number still looks like a phone).
    #
    # Must remain unique-per-placeholder to avoid collisions in the content-script vault.
    if counter:
        return f"⟦REDACTED_{counter}⟧"

    if entity_type == "PERSON":
        return random.choice(_PERSON_NAMES)

    if entity_type == "PHONE_NUMBER":
        return "9" + str(random.randint(100_000_000, 999_999_999))

    if entity_type == "IN_AADHAAR":
        return (
            f"{random.randint(1000, 9999)} "
            f"{random.randint(1000, 9999)} "
            f"{random.randint(1000, 9999)}"
        )

    if entity_type == "IN_PAN":
        letters = string.ascii_uppercase
        return (
            "".join(random.choices(letters, k=5))
            + "".join(random.choices(string.digits, k=4))
            + random.choice(letters)
        )

    if entity_type == "EMAIL_ADDRESS":
        return f"user{random.randint(1000, 9999)}@example.com"

    if entity_type == "UPI_ID":
        return f"user{random.randint(1000, 9999)}@okaxis"

    # Unknown type — return a safe sentinel.
    return "⟦REDACTED⟧"


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.options("/anonymize")
@router.options("/consent-profile")
async def options_handler(response: Response) -> Response:
    """Handle pre-flight CORS requests from the browser extension."""
    _cors(response)
    return Response(status_code=204, headers=dict(response.headers))


@router.post("/anonymize")
async def anonymize(
    payload: ExtensionAnonymizePlaceholderRequest,
    response: Response,
) -> JSONResponse:
    """
    Swap placeholder tokens for random dummy values.

    Input:  { "entity_refs": ["[PERSON_1]", "[PHONE_NUMBER_2]"], "session_id": "..." }
    Output: { "dummies": { "[PERSON_1]": "Alex Smith", ... }, "session_id": "..." }

    No real PII ever enters this function.
    """
    _cors(response)

    logger.info(
        "Extension anonymize: %d placeholder(s) for session %s",
        len(payload.entity_refs),
        payload.session_id,
    )

    dummies = {ref: _generate_dummy(ref) for ref in payload.entity_refs}

    return JSONResponse(
        content={"dummies": dummies, "session_id": payload.session_id},
        headers=dict(response.headers),
    )


@router.get("/consent-profile")
async def consent_profile(
    user_id: str,
    request: Request,
    response: Response,
) -> JSONResponse:
    """
    Return the user's PII consent profile.

    Falls back to DEFAULT_PII_PROFILE when Redis is unreachable or the
    user has no stored preferences.
    """
    _cors(response)

    profile: dict | None = None
    try:
        redis_client = request.app.state.redis_client
        profile = await get_consent_cache(
            redis_client,
            user_id=user_id,
            purpose="extension_pii_masking",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("extension consent-profile cache lookup failed: %s", exc)

    return JSONResponse(
        content=profile if profile is not None else DEFAULT_PII_PROFILE,
        headers=dict(response.headers),
    )
