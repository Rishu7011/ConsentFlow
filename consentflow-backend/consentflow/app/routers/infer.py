"""
routers/infer.py — Dummy inference endpoints for testing the ConsentMiddleware.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/infer", tags=["inference"])


@router.post("/predict")
async def predict_model(request: Request) -> dict[str, Any]:
    """
    Dummy endpoint representing an AI model inference call.

    This route sits behind the `ConsentMiddleware` (mapped to `/infer`).
    If the request reaches this function, the user has valid consent.
    """
    body = await request.json()
    user_id = body.get("user_id") or request.headers.get("X-User-ID")
    
    logger.info("Executing inference for user_id=%s", user_id)
    
    return {
        "status": "success",
        "message": "Inference completed safely.",
        "user_id": user_id,
        "prediction": "dummy_output",
    }
