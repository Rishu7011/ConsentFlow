"""
main.py — FastAPI application entry point.

Lifespan:
  - Startup:  create asyncpg pool + Redis client + Kafka producer, run DB migrations
  - Shutdown: gracefully close Kafka producer, Redis client, DB pool (reverse order)
"""
from __future__ import annotations

import logging
import pathlib
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware


from consentflow.app.cache import (
    check_redis,
    close_redis_client,
    create_redis_client,
)
from consentflow.app.config import settings
from consentflow.app.db import check_postgres, close_pool, create_pool
from consentflow.app.kafka_producer import (
    close_kafka_producer,
    create_kafka_producer,
)
from consentflow.app.models import HealthResponse
from consentflow.app.routers import consent as consent_router
from consentflow.app.routers import webhook as webhook_router
from consentflow.app.routers import infer as infer_router
from consentflow.app.routers import audit as audit_router
from consentflow.app.routers import users as users_router
from consentflow.app.routers import dashboard as dashboard_router
from consentflow.app.routers.policy import router as policy_router
from consentflow.app.routers import chat as chat_router
from consentflow.inference_gate import ConsentMiddleware



# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = pathlib.Path(__file__).parent.parent / "migrations"


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context manager.

    Startup order:
        1. PostgreSQL pool + migrations
        2. Redis client
        3. Kafka producer

    Shutdown order (reverse of startup):
        3. Kafka producer
        2. Redis client
        1. PostgreSQL pool
    """
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting ConsentFlow (env=%s)", settings.app_env)

    # 0. OpenTelemetry (optional — skipped in tests / when otel_enabled=False)
    if settings.otel_enabled:
        from consentflow.telemetry import configure_otel  # noqa: PLC0415
        configure_otel(settings.otel_endpoint, settings.otel_service_name)

    # 1. PostgreSQL
    pool = await create_pool()
    app.state.db_pool = pool

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    async with pool.acquire() as conn:
        for migration in migration_files:
            logger.info("Applying migration: %s", migration.name)
            sql = migration.read_text(encoding="utf-8")
            await conn.execute(sql)

    # 2. Redis
    redis_client = await create_redis_client()
    app.state.redis_client = redis_client

    # 3. Kafka producer
    kafka_producer = await create_kafka_producer()
    app.state.kafka_producer = kafka_producer

    logger.info("ConsentFlow startup complete ✓")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down ConsentFlow…")
    await close_kafka_producer(app.state.kafka_producer)
    await close_redis_client(app.state.redis_client)
    await close_pool(app.state.db_pool)
    logger.info("ConsentFlow shutdown complete ✓")


# ── Application factory ────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="ConsentFlow",
        description=(
            "Consent-enforcement middleware for AI pipelines. "
            "Provides a foundational data layer and REST API for managing "
            "user consent records, with real-time revocation propagation via Kafka."
        ),
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Middlewares ───────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        ConsentMiddleware,
        protected_prefixes=["/infer"],
        purpose="inference",
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(users_router.router)    # prefix="/users"
    app.include_router(consent_router.router)
    app.include_router(webhook_router.router)  # prefix="/webhook"
    app.include_router(infer_router.router)
    app.include_router(audit_router.router)   # prefix="/audit" (Step 7)
    app.include_router(dashboard_router.router)
    app.include_router(policy_router)          # prefix="/policy" (Gate 05)
    app.include_router(chat_router.router)     # prefix="/chat"  (Plan 1.5)

    # ── Health endpoint ───────────────────────────────────────────────────────
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["observability"],
        summary="Liveness check",
        description="Returns the health of Postgres, Redis, Kafka, and OTel.",
    )
    async def health(request: Request) -> HealthResponse:
        pg_status = await check_postgres(request.app.state.db_pool)
        redis_status = await check_redis(request.app.state.redis_client)
        
        # Simple Kafka check based on connection state
        # (aiokafka doesn't have a simple ping, but we check if the object exists)
        kafka_status = "ok" if request.app.state.kafka_producer else "error"
        
        # OTel is based on configuration
        otel_status = "ok" if getattr(settings, "otel_enabled", False) else "disabled"
        
        overall = "ok" if pg_status == "ok" and redis_status == "ok" and kafka_status == "ok" else "degraded"
        return HealthResponse(
            status=overall,
            postgres=pg_status,
            redis=redis_status,
            kafka=kafka_status,
            otel=otel_status,
        )

    return app


app = create_app()
