from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "consentflow"
    postgres_user: str = "consentflow"
    postgres_password: str = "consentflow"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Cache TTL (seconds)
    consent_cache_ttl: int = 60

    # ── Kafka ──────────────────────────────────────────────────────────────────
    # Internal broker address used by the app container (kafka:9092).
    # For local dev outside Docker use localhost:29092.
    kafka_broker_url: str = "localhost:29092"
    # Topic where consent-revocation events are published.
    kafka_topic_revoke: str = "consent.revoked"

    # ── Step 7: OpenTelemetry ──────────────────────────────────────────────────
    # Set otel_enabled=true in docker-compose env to activate OTLP export.
    # Defaults to False so existing tests never need a running OTel collector.
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"  # OTLP gRPC
    otel_service_name: str = "consentflow"

    # ── Gemini AI (RAG chat) ───────────────────────────────────────────────────
    # Get a free key at: https://aistudio.google.com/app/apikey
    gemini_api_key: str = ""

    # ── Mistral AI (Fallback) ──────────────────────────────────────────────────
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"

    # ── Gate 05: Policy Auditor (Ollama local LLM) ────────────────────────────
    # Ollama OpenAI-compatible endpoint. Override in .env or docker-compose env.
    # Docker users: set OLLAMA_BASE_URL=http://host.docker.internal:11434
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma2:2b"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def asyncpg_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
