"""
consentflow/inference_gate.py — FastAPI middleware for inference-time consent enforcement.

How it works
------------
``ConsentMiddleware`` is a Starlette ``BaseHTTPMiddleware`` installed on the
FastAPI app.  It only activates for paths that start with any of the prefixes in
``protected_prefixes`` (default: ``["/infer"]``).  All other paths are passed
through untouched — so existing /consent, /webhook, /health routes are
unaffected.

User-ID extraction (in order)
------------------------------
1. ``X-User-ID`` HTTP header  — works for every HTTP method, zero body cost.
2. JSON body field ``user_id`` — useful when the caller POSTs a JSON payload
   and cannot set custom headers.

Responses
---------
* 400 Bad Request   — ``user_id`` could not be found in the request.
* 403 Forbidden     — user exists but consent is revoked.
* passthrough       — consent is granted; the original handler runs normally.

Configuration
-------------
Pass keyword arguments to ``ConsentMiddleware`` via ``app.add_middleware()``:

    app.add_middleware(
        ConsentMiddleware,
        protected_prefixes=["/infer", "/predict"],
        purpose="inference",
    )
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from consentflow.sdk import is_user_consented

logger = logging.getLogger(__name__)

# Default path prefixes that require consent enforcement
_DEFAULT_PROTECTED_PREFIXES: list[str] = ["/infer"]


class ConsentMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that enforces inference-time consent.

    Parameters
    ----------
    app:               The wrapped ASGI application.
    protected_prefixes: Path prefixes to guard (default: ``["/infer"]``).
    purpose:           Consent purpose string checked against the store
                       (default: ``"inference"``).
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        protected_prefixes: list[str] | None = None,
        purpose: str = "inference",
    ) -> None:
        super().__init__(app)
        self._prefixes: list[str] = protected_prefixes or _DEFAULT_PROTECTED_PREFIXES
        self._purpose: str = purpose

    # ── Path filter ────────────────────────────────────────────────────────────

    def _is_protected(self, path: str) -> bool:
        """Return True iff *path* falls under a protected prefix."""
        return any(path.startswith(prefix) for prefix in self._prefixes)

    # ── User-ID extraction ─────────────────────────────────────────────────────

    @staticmethod
    async def _extract_user_id(request: Request) -> str | None:
        """
        Try to resolve a user_id from the request.

        Priority
        --------
        1. ``X-User-ID`` header   (fast, no body read)
        2. JSON body ``user_id``  (POST / PUT requests with JSON payload)

        Returns ``None`` when neither source provides a value.
        """
        # 1. Header
        header_uid = request.headers.get("X-User-ID")
        if header_uid:
            return header_uid.strip()

        # 2. JSON body — only try on methods that typically carry a body
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    payload: dict[str, Any] = json.loads(body_bytes)
                    uid = payload.get("user_id")
                    if uid:
                        # Stash the payload for later use (e.g. dynamic purpose)
                        request.state.payload = payload
                        return str(uid).strip()
            except (json.JSONDecodeError, Exception):  # noqa: BLE001
                pass  # malformed body — fall through to 400

        return None

    # ── Middleware entry point ─────────────────────────────────────────────────

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        """Intercept the request, enforce consent, then forward or reject."""
        path = request.url.path

        # Fast-path: unprotected routes skip all consent logic
        if not self._is_protected(path):
            return await call_next(request)

        # ── 1. Extract user_id ─────────────────────────────────────────────
        user_id = await self._extract_user_id(request)

        if not user_id:
            logger.warning(
                "Inference gate BLOCKED (no user_id) — path=%s method=%s",
                path,
                request.method,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Missing user identifier. "
                    "Supply X-User-ID header or 'user_id' in the JSON body."
                },
            )

        # ── 2. Consent check ───────────────────────────────────────────────
        # Reuse shared connections from app.state when available (production);
        # fall back to creating ad-hoc connections when state is absent (tests
        # that patch is_user_consented directly bypass this entirely).
        redis_client = getattr(request.app.state, "redis_client", None)
        db_pool = getattr(request.app.state, "db_pool", None)
        
        # Determine purpose (dynamic from payload or fallback to configured)
        target_purpose = self._purpose
        if hasattr(request.state, "payload") and isinstance(request.state.payload, dict):
            target_purpose = request.state.payload.get("purpose", self._purpose)

        try:
            consented = await is_user_consented(
                user_id,
                target_purpose,
                redis_client=redis_client,
                db_pool=db_pool,
            )
        except Exception as exc:  # noqa: BLE001
            # Consent-check failure → deny (fail-closed)
            logger.error(
                "Inference gate: consent check error user_id=%s error=%s — denying",
                user_id,
                exc,
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Consent service unavailable. Request denied."},
            )

        if not consented:
            logger.info(
                "Inference gate BLOCKED (revoked) — user_id=%s path=%s",
                user_id,
                path,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Inference blocked — consent revoked for this user.",
                    "user_id": user_id,
                },
            )

        logger.debug(
            "Inference gate ALLOW — user_id=%s path=%s",
            user_id,
            path,
        )
        return await call_next(request)
