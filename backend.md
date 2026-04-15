# ConsentFlow — Backend Reference

> FastAPI 0.115 · Python 3.12 · asyncpg · Redis · Kafka · Presidio · LangChain · Gemini · Mistral · Ollama

---

## Project Layout

```
consentflow-backend/
├── consentflow/
│   ├── __init__.py
│   ├── anonymizer.py          # Presidio PII detection + redaction (18 entity types)
│   ├── dataset_gate.py        # Dataset consent gate (MLflow + PII scrub)
│   ├── gemini_client.py       # Multi-tier AI client: Mistral → Gemini → Ollama
│   ├── inference_gate.py      # ASGI ConsentMiddleware (blocks /infer on revocation)
│   ├── langchain_gate.py      # LangChain callback equivalent of inference_gate
│   ├── memory_store.py        # RAG knowledge base per user (fact extraction + freeze)
│   ├── mlflow_utils.py        # MLflow experiment/run helpers
│   ├── monitoring_gate.py     # Evidently-based drift monitor
│   ├── otel_dataset_gate.py   # OTel-instrumented dataset gate wrapper
│   ├── otel_inference_gate.py # OTel-instrumented inference gate wrapper
│   ├── otel_monitoring_gate.py# OTel-instrumented monitoring gate wrapper
│   ├── otel_training_gate.py  # OTel-instrumented training gate wrapper
│   ├── policy_auditor.py      # Gate 05: LLM ToS scanner (Gemini → Mistral → Ollama)
│   ├── sdk.py                 # Thin consent SDK: is_user_consented()
│   ├── telemetry.py           # OTel SDK bootstrap
│   ├── training_gate.py       # Kafka consumer → MLflow quarantine
│   ├── app/
│   │   ├── cache.py           # Redis consent cache helpers
│   │   ├── config.py          # Pydantic settings (reads .env)
│   │   ├── db.py              # asyncpg pool factory
│   │   ├── kafka_producer.py  # aiokafka producer + publish_revocation()
│   │   ├── main.py            # FastAPI app factory + lifespan
│   │   ├── models.py          # All Pydantic request/response models
│   │   └── routers/
│   │       ├── audit.py       # GET /audit/trail
│   │       ├── chat.py        # POST /chat/message + state/history
│   │       ├── consent.py     # POST/GET /consent + /consent/revoke
│   │       ├── dashboard.py   # GET /dashboard/stats
│   │       ├── infer.py       # POST /infer/predict (protected)
│   │       ├── policy.py      # POST /policy/scan + GET /policy/scans
│   │       ├── users.py       # POST/GET /users
│   │       └── webhook.py     # POST /webhook/consent-revoke
│   └── migrations/
│       ├── 001_init.sql              # users + consent_records tables
│       ├── 002_audit_log.sql         # audit_log table
│       ├── 003_seed_demo_user.sql    # demo UUID seed
│       ├── 004_policy_scans.sql      # policy_scans table
│       ├── 005_chat_memory.sql       # user_memory + chat_log tables
│       └── 006_consent_freeze_log.sql# consent_freeze_log table
├── tests/                     # pytest suite
├── grafana/                   # Grafana provisioning (dashboard + datasource)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml             # uv/hatch project (version 0.3.0)
├── otel-collector-config.yaml
├── seed_db.py
└── cleanup_db.py
```

---

## App Startup (Lifespan)

`app/main.py` — `create_app()` factory, `lifespan()` context manager.

**Startup order:**
1. OpenTelemetry SDK (if `otel_enabled=True`)
2. asyncpg pool → auto-run all `migrations/*.sql` in sorted order
3. Redis client (`aioredis`)
4. aiokafka producer

**Shutdown order (reverse):** Kafka → Redis → asyncpg pool

**Middlewares:**
- `CORSMiddleware` — origins: `http://localhost:3000`, `http://localhost:3001`
- `ConsentMiddleware` — protects `/infer` prefix; checks consent before every request

---

## Configuration (`app/config.py`)

All settings read from `.env` via `pydantic-settings`.

```python
class Settings(BaseSettings):
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
    consent_cache_ttl: int = 60        # seconds

    # Kafka
    kafka_broker_url: str = "localhost:29092"
    kafka_topic_revoke: str = "consent.revoked"

    # OTel
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "consentflow"

    # AI: Gemini (Tier 2 chat + policy scan)
    gemini_api_key: str = ""

    # AI: Mistral (Tier 1 primary)
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"

    # AI: Ollama (Tier 3 local fallback)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma2:2b"
```

---

## Routers

### `routers/consent.py` — Consent CRUD

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/consent` | List 1000 most recent records |
| `POST` | `/consent` | Upsert record; **if status=granted**, automatically deletes row from `consent_freeze_log` to unfreeze memory |
| `POST` | `/consent/revoke` | Set all rows for user+purpose to `revoked`; invalidates Redis |
| `GET` | `/consent/{user_id}/{purpose}` | Redis-first lookup (TTL 60 s); Postgres fallback; writes back to cache |

**Key implementation detail — unfreeze on grant:**
```python
if body.status.value == "granted":
    await conn.execute(
        "DELETE FROM consent_freeze_log WHERE user_id = $1",
        str(body.user_id)
    )
```
This is what allows the frontend "Restore Consent" button to unfreeze the memory bank without a separate API call.

---

### `routers/webhook.py` — Webhook Ingress

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhook/consent-revoke` | OneTrust-style revocation signal |
| `POST` | `/webhook` | Frontend alias (same handler) |

**Payload (camelCase OneTrust format):**
```json
{
  "userId": "<uuid>",
  "purpose": "model_training",
  "consentStatus": "revoked",
  "timestamp": "2026-04-30T12:00:00Z"
}
```

**Processing pipeline:**
1. Validate `consentStatus == "revoked"` (422 otherwise)
2. Parse `userId` as UUID (422 if malformed)
3. DB upsert `consent_records` (INSERT … ON CONFLICT — idempotent)
4. Redis invalidate cache key
5. Kafka publish `consent.revoked` event
6. Write `consent_freeze_log` (records `frozen_at_count = memory_store.get_memory_count()`)
7. Return `200` on full success, `207` if Kafka failed

**Idempotency:** Duplicate webhooks for the same user+purpose are safe — the DB upsert always sets `revoked` and the cache is always invalidated.

---

### `routers/chat.py` — RAG Chat

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat/message` | Main chat endpoint — Presidio scan → consent check → memory → AI → log |
| `GET` | `/chat/state/{user_id}` | Returns `memories`, `frozen`, `frozen_at_count`, `consent_status` |
| `DELETE` | `/chat/state/{user_id}` | Demo reset — clears `user_memory`, `chat_log`, `consent_freeze_log`, `consent_records` |
| `GET` | `/chat/history` | Paginated chat log (newest-first, max 500 rows) |

**`POST /chat/message` — 9-step flow:**

```
Step 1: Presidio PII scan (always)
        → analyzer.analyze(text, entities=ALL_PII_ENTITIES)
        → anonymizer.anonymize(text) → message_redacted

Step 2: Consent check
        → Redis cache (key: consent:{user_id}:model_training)
        → Postgres fallback (latest row for user+purpose)
        → Default: "revoked" (fail-closed)

Step 3: Memory update (ONLY if consent == "granted")
        → memory_store.extract_and_store(pool, user_id, message, pii_entities)

Step 4: Retrieve memories (always — frozen set returned after revocation)
        → memory_store.get_memories(pool, user_id)

Step 5: Call AI chain
        → gemini_client.chat(memories, prompt)
        → Mistral → Gemini → Ollama fallback

Step 6: Log to chat_log
        → stores original message if granted, redacted if revoked

Step 7: Log to audit_log
        → action_taken: "memory_stored" or "memory_blocked"

Step 8: Read freeze state
        → consent_freeze_log lookup → (frozen: bool, frozen_at_count: int|None)

Step 9: Return ChatResponse
        → reply, trained_on_message, consent_status, pii_detected,
           message_redacted, memories_used, memory_state
```

**Consent purpose for chat:** `model_training`

---

### `routers/policy.py` — Policy Auditor (Gate 05)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/policy/scan` | LLM scan of a third-party ToS/privacy policy |
| `GET` | `/policy/scans` | List all past scans |
| `GET` | `/policy/scans/{scan_id}` | Get scan result by UUID |

Delegates to `PolicyAuditor.scan()` in `policy_auditor.py`.

---

### `routers/audit.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/audit/trail` | Query `audit_log` with optional `user_id`, `gate_name`, `limit` filters |
| `GET` | `/audit` | Alias |

---

### `routers/dashboard.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/dashboard/stats` | Returns `users`, `granted`, `blocked`, `purposes`, `checks_24h_*`, `checks_sparkline`, `policy_scans_total`, `policy_scans_critical` |

---

### `routers/users.py`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/users` | Create user (201) |
| `GET` | `/users` | List all users with derived consent status |
| `GET` | `/users/{user_id}` | Get user by UUID |

---

### `routers/infer.py`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/infer/predict` | Protected dummy inference endpoint |

The entire `/infer` prefix is intercepted by `ConsentMiddleware` before this handler runs.

---

## Core Modules

### `anonymizer.py` — Presidio PII Engine

Singletons loaded once on import:
- `analyzer` — `AnalyzerEngine` with `en_core_web_lg` spaCy model
- `anonymizer` — `AnonymizerEngine`
- `ALL_PII_ENTITIES` — 18-entity list

**Custom recognizers added:**

| Entity | Pattern/DenyList |
|--------|------------------|
| `IN_AADHAAR` | 12-digit Aadhaar regex |
| `IN_PAN` | 10-char PAN card regex |
| `IN_PHONE` | Indian mobile (+91 optional) |
| `AGE` | "I'm 24", "aged 30", "24 years old" |
| `MEDICAL_CONDITION` | deny-list: diabetic, hypertension, PCOD… |
| `FINANCIAL_INFO` | deny-list: salary, LPA, CTC, broke… |
| `RELATIONSHIP_STATUS` | deny-list: married, single, girlfriend… |
| `PERSON` (demo) | pattern: Rishabh, Rishu (demo names) |

**Standard entities also detected:**
`PERSON`, `DATE_TIME`, `LOCATION`, `IP_ADDRESS`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `URL`, `CREDIT_CARD`, `IBAN_CODE`, `PASSPORT`, `DRIVER_LICENSE`, `US_SSN`, `NRP`

Redaction operator: `replace` with `<REDACTED>`.

---

### `memory_store.py` — RAG Knowledge Base

Singleton `memory_store = MemoryStore()`.

**Before consent revocation:** `extract_and_store()` is called on every chat message. Facts are extracted using 7 rule groups (identity, location, professional, health, relationship, financial, preference) with 50+ regex patterns.

**After consent revocation:** `extract_and_store()` is never called. `get_memories()` returns the same frozen set — so Gemini's context is permanently fixed at the moment of revocation.

**`consent_freeze_log`** records `frozen_at_count` at revocation time so the frontend can display "N facts (frozen forever)".

**Key methods:**

| Method | Description |
|--------|-------------|
| `extract_and_store(pool, user_id, message, pii_entities)` | Extract facts, dedup, persist to `user_memory` |
| `get_memories(pool, user_id)` | All memories, ordered ASC by `created_at` |
| `get_memory_count(pool, user_id)` | COUNT for freeze log |
| `clear_memories(pool, user_id)` | Delete all memory, chat, freeze log, consent records |
| `get_state(pool, user_id, frozen, frozen_at_count)` | Full state dict for frontend polling |

**Fact deduplication:** prefix-based (`fact[:30]` not in `existing_prefixes`).

---

### `gemini_client.py` — Multi-Tier AI Client

```
Tier 1: Mistral (mistral-small-latest) — primary
Tier 2: Gemini 2.0 Flash              — first fallback
Tier 3: Ollama (gemma2:2b)            — local final fallback
```

Built with LangChain `with_fallbacks()` — automatic cascade on any error:

```python
model_chain = mistral_model.with_fallbacks([
    gemini_model.with_fallbacks([ollama_model])
])
chain = prompt_template | model_chain
response = await chain.ainvoke({"memory_lines": ..., "user_message": ...})
```

System prompt injects user memories as bullet points. Response capped at 200 tokens.

---

### `inference_gate.py` — ASGI Consent Middleware

`ConsentMiddleware(BaseHTTPMiddleware)` — installed on the FastAPI app.

**Protected prefix:** `/infer` (configurable)

**User-ID extraction order:**
1. `X-User-ID` header (fast, no body read)
2. `user_id` field in JSON body (POST/PUT/PATCH only)

**Response codes:**
- `400` — no user_id found
- `403` — consent revoked
- `503` — consent service unavailable (fail-closed)
- passthrough — consent granted

---

### `policy_auditor.py` — Gate 05

**Scan pipeline:**
1. Fetch policy text (URL or raw text; HTML stripped, max 12,000 chars)
2. SHA-256 hash for deduplication
3. Call LangChain chain: Gemini → Mistral → Ollama
4. Parse JSON findings (strips markdown fences, validates severities)
5. Recompute `overall_risk_level` as max of all finding severities (safety net)
6. Persist to `policy_scans`
7. Write `audit_log` row
8. Return `PolicyScanResult`

**7 scanning categories:**
1. Training on Inputs
2. Broad Data Sharing
3. Irrevocable License Grant
4. Opt-Out Only (no opt-in)
5. Retroactive Policy Changes
6. Data Retention After Deletion Request
7. Cross-Context Behavioral Tracking

**Severity levels:** `low`, `medium`, `high`, `critical`

---

## Database Schema

### `users`
```sql
id         UUID PRIMARY KEY DEFAULT gen_random_uuid()
email      TEXT NOT NULL UNIQUE
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

### `consent_records`
```sql
id         UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
data_type  TEXT NOT NULL
purpose    TEXT NOT NULL
status     TEXT NOT NULL CHECK (status IN ('granted','revoked'))
updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
UNIQUE (user_id, purpose, data_type)
INDEX (user_id, purpose, status)
```

### `audit_log`
```sql
id             UUID PRIMARY KEY DEFAULT gen_random_uuid()
event_time     TIMESTAMPTZ NOT NULL DEFAULT NOW()
user_id        TEXT NOT NULL        -- denormalized TEXT
gate_name      TEXT NOT NULL        -- e.g. training_gate, policy_auditor
action_taken   TEXT NOT NULL        -- e.g. memory_stored, memory_blocked
consent_status TEXT NOT NULL
purpose        TEXT
metadata       JSONB
trace_id       TEXT
INDEX (user_id), INDEX (event_time DESC), INDEX (gate_name)
```

### `policy_scans`
```sql
id                 UUID PRIMARY KEY DEFAULT gen_random_uuid()
scanned_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
integration_name   TEXT NOT NULL
policy_url         TEXT
policy_text_hash   TEXT NOT NULL   -- SHA-256 dedup key
overall_risk_level TEXT NOT NULL
findings_count     INTEGER NOT NULL
findings           JSONB NOT NULL
raw_summary        TEXT NOT NULL
```

### `user_memory`
```sql
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id      UUID NOT NULL REFERENCES users(id)
memory_text  TEXT NOT NULL
source_msg   TEXT NOT NULL
pii_detected TEXT[]
created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

### `chat_log`
```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
event_time       TIMESTAMPTZ NOT NULL DEFAULT NOW()
user_id          UUID NOT NULL REFERENCES users(id)
message          TEXT NOT NULL   -- original or redacted if revoked
message_redacted TEXT NOT NULL   -- Presidio-redacted
reply            TEXT NOT NULL
trained          BOOLEAN NOT NULL DEFAULT FALSE
memory_used      TEXT[]
pii_detected     TEXT[]
consent_status   TEXT NOT NULL
```

### `consent_freeze_log`
```sql
user_id          UUID PRIMARY KEY REFERENCES users(id)
frozen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
frozen_at_count  INTEGER NOT NULL
```

Written by `POST /webhook` on revocation. Deleted by `POST /consent` when `status=granted`.

---

## Kafka Integration

**Topic:** `consent.revoked`
**Producer:** `publish_revocation()` in `app/kafka_producer.py`
**Consumer:** `TrainingGateConsumer` in `training_gate.py` (standalone process)

**Message schema:**
```json
{
  "event": "consent.revoked",
  "user_id": "<uuid>",
  "purpose": "<string>",
  "timestamp": "<iso8601>"
}
```

To run the training gate consumer standalone:
```bash
python -m consentflow.training_gate
```

---

## Redis Cache

**Key pattern:** `consent:{user_id}:{purpose}`
**TTL:** `CONSENT_CACHE_TTL` seconds (default 60)
**Value:** JSON with `user_id`, `purpose`, `status`, `updated_at`

Cache is **invalidated** on every write to `consent_records` (upsert, revoke, webhook).
Cache is **populated** lazily on `GET /consent/{user_id}/{purpose}` cache miss.

---

## Observability

OTel is **disabled by default** (`otel_enabled=false`). Enable in `docker-compose.yml` environment section.

| Span name | Gate |
|-----------|------|
| `dataset_gate.check` | Dataset gate |
| `inference_gate.check` | Inference gate |
| `training_gate.quarantine` | Training gate |
| `monitoring_gate.check` | Drift monitor |

Common span attributes: `gate_name`, `consent_status`, `action_taken`, `user_id`, `trace_id`

Grafana dashboard (uid: `consentflow-observability`) is provisioned automatically via `grafana/` directory.

---

## Python Dependencies

```toml
# Core
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
asyncpg>=0.29.0
redis[hiredis]>=5.0.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
aiokafka>=0.11.0

# PII
presidio-analyzer>=2.2.354
presidio-anonymizer>=2.2.354
spacy>=3.7.0   # requires: python -m spacy download en_core_web_lg

# AI / LangChain
langchain-core>=0.2.0
langchain-google-genai>=1.0.0
langchain-mistralai>=0.1.0
langchain-ollama>=0.1.0

# ML
mlflow>=2.13.0
evidently>=0.4.0

# Observability
opentelemetry-sdk>=1.24.0
opentelemetry-exporter-otlp-proto-grpc>=1.24.0

# HTTP
httpx>=0.27.0
```

---

## Running Locally (Without Docker)

```bash
cd consentflow-backend

# Install dependencies
uv sync

# Download spaCy model
uv run python -m spacy download en_core_web_lg

# Run the API (requires Postgres, Redis, Kafka running)
uv run uvicorn consentflow.app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
uv run pytest
uv run pytest --cov=consentflow --cov-report=term-missing
```
