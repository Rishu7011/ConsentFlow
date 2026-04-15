"""
consentflow/langchain_gate.py — LangChain callback handler for consent enforcement.

Hooks into LangChain's callback system to block LLM execution for users whose
consent has been revoked, before the model call is dispatched.

Usage
-----
    from consentflow.langchain_gate import ConsentCallbackHandler

    handler = ConsentCallbackHandler(user_id="<uuid>", purpose="inference")

    llm = ChatOpenAI(callbacks=[handler])
    # or pass at invocation time:
    llm.invoke("Hello", config={"callbacks": [handler]})

If the user's consent is revoked, ``on_llm_start`` raises
``ConsentRevokedException`` before the LLM API call is made.

Async support
-------------
Both sync (``on_llm_start``) and async (``on_llm_start_async``) hooks are
implemented so the handler works in both synchronous chains and async LCEL
pipelines.

Dependencies
------------
Requires ``langchain-core>=0.2.0`` (installed via pyproject.toml).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from consentflow.sdk import is_user_consented

logger = logging.getLogger(__name__)


# ── Custom exception ───────────────────────────────────────────────────────────


class ConsentRevokedException(RuntimeError):
    """
    Raised when a LangChain LLM call is attempted for a user whose consent
    has been revoked.

    Attributes
    ----------
    user_id: The user whose consent was checked.
    purpose: The consent purpose that was checked.
    """

    def __init__(self, user_id: str, purpose: str) -> None:
        self.user_id = user_id
        self.purpose = purpose
        super().__init__(
            f"LLM call blocked — consent revoked for user_id={user_id!r} "
            f"purpose={purpose!r}."
        )


# ── Callback handler ───────────────────────────────────────────────────────────


class ConsentCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler that enforces consent before every LLM call.

    Parameters
    ----------
    user_id:      UUID string of the requesting user.
    purpose:      Consent purpose to check (default: ``"inference"``).
    redis_client: Optional shared Redis client for cache lookups.
    db_pool:      Optional shared asyncpg pool for DB fallback lookups.

    Raises
    ------
    ConsentRevokedException
        If the user's consent for *purpose* is revoked or absent.
    """

    def __init__(
        self,
        user_id: str | UUID,
        *,
        purpose: str = "inference",
        redis_client: Any = None,
        db_pool: Any = None,
    ) -> None:
        super().__init__()
        self._user_id = str(user_id)
        self._purpose = purpose
        self._redis_client = redis_client
        self._db_pool = db_pool

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _check(self) -> None:
        """Perform the consent check and raise if revoked."""
        consented = await is_user_consented(
            self._user_id,
            self._purpose,
            redis_client=self._redis_client,
            db_pool=self._db_pool,
        )
        if not consented:
            logger.info(
                "LangChain gate: blocking LLM call for user_id=%s purpose=%s",
                self._user_id,
                self._purpose,
            )
            raise ConsentRevokedException(self._user_id, self._purpose)
        logger.debug(
            "LangChain gate: consent granted for user_id=%s purpose=%s",
            self._user_id,
            self._purpose,
        )

    # ── Sync hook (used by synchronous LangChain chains) ──────────────────────

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Called before every LLM invocation in synchronous chains."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside a running loop (e.g. Jupyter / FastAPI) — schedule
                # as a task and wait; this is safe in most LCEL scenarios.
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, self._check())
                    future.result()
            else:
                loop.run_until_complete(self._check())
        except ConsentRevokedException:
            raise  # Re-raise cleanly
        except Exception as exc:  # noqa: BLE001
            logger.error("LangChain gate: consent check error: %s — denying", exc)
            raise ConsentRevokedException(self._user_id, self._purpose) from exc

    # ── Async hook (used by async LCEL pipelines / astream) ───────────────────

    async def on_llm_start_async(  # type: ignore[override]
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Called before every LLM invocation in async chains."""
        await self._check()
