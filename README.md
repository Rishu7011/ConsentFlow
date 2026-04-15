# ConsentFlow

> **Real-time consent enforcement across your entire AI pipeline.**

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.2-black)](https://nextjs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

ConsentFlow is a full-stack middleware system that enforces user consent revocation across an AI pipeline in real time. When a user revokes consent, ConsentFlow propagates the revocation instantly — from API to cache to event bus — and freezes the RAG memory bank, blocks inference, scrubs datasets, and quarantines training runs.

---

## What it does

A user revokes consent once — via the interactive dashboard, CMP webhook, or direct API. ConsentFlow:

1. **Writes** the revocation to PostgreSQL (authoritative record)
2. **Invalidates** the Redis cache entry for that user+purpose
3. **Publishes** a `consent.revoked` event to Apache Kafka
4. **Writes** a freeze log entry recording the memory count at revocation time
5. **Enforces** the revocation at every gate in the AI pipeline:

| Gate | Layer | Enforcement |
|------|-------|-------------|
| **Training Gate** | Model training | Stops writing new facts to the RAG memory store |
| **Presidio PII** | Message scanning | Redacts PII (`<REDACTED>`) in all messages after revocation |
| **Dataset Gate** | Data prep | Anonymizes revoked users' data before MLflow registration |
| **Inference Gate** | Live serving | ASGI middleware returns `403` in <5 ms (Redis cache hit) |
| **Drift Monitor** | Monitoring | Flags revoked-user samples in Evidently drift windows |
| **Policy Auditor** | Compliance | LLM-based ToS scanner for third-party AI integrations |

---

## Architecture

```
User revokes consent (Dashboard or API)
        │
        ▼
POST /webhook/consent-revoke
        ├─► PostgreSQL  (upsert consent_records → revoked)
        ├─► Redis       (invalidate cache key)
        ├─► consent_freeze_log (snapshot memory count)
        └─► Kafka       (publish consent.revoked)
                ├─► Training Gate   (memory writes blocked)
                ├─► Presidio Gate   (PII redacted in messages)
                ├─► Dataset Gate    (PII scrubbed from datasets)
                ├─► Inference Gate  (403 Forbidden)
                ├─► Drift Monitor   (severity alert)
                └─► Policy Auditor  (LLM ToS scan + DB log)

POST /consent (status=granted)
        └─► Clears consent_freeze_log (memory bank unfreezes)
```

The **Next.js 16 frontend** provides a three-panel interactive dashboard: live RAG Memory Bank, real-time AI chat, and an animated Pipeline Gates view with live audit ticker.

---

## Quick Start

### Prerequisites

- Docker + Docker Compose v2
- Node.js 20+ (for the frontend)
- Python 3.12+ and `uv` (for local backend dev only)

### 1. Clone and configure

```bash
git clone https://github.com/Rishu7011/ConsentFlow-
cd ConsentFlow-/consentflow-backend
cp .env.example .env          # Linux/Mac
copy .env.example .env        # Windows PowerShell
```

Edit `.env`. At minimum set `GEMINI_API_KEY` for AI chat. See [Environment variables](#environment-variables).

### 2. (Apple Silicon only) Add platform pin

In `docker-compose.yml`, add `platform: linux/amd64` to the `zookeeper` and `kafka` services.

### 3. Start the full backend stack

```bash
cd consentflow-backend
docker compose up --build
```

Starts PostgreSQL 16, Redis 7, Zookeeper, Kafka, the ConsentFlow API, OTel Collector, and Grafana. Migrations `001`–`006` are auto-applied at startup.

### 4. Start the frontend

```bash
cd consentflow-frontend
npm install
npm run dev
```

Open **http://localhost:3000**.

### 5. Verify health

```bash
curl http://localhost:8000/health
# → {"status":"ok","postgres":"ok","redis":"ok","kafka":"ok","otel":"disabled"}
```

### Service URLs

| Service | URL |
|---------|-----|
| **Frontend dashboard** | http://localhost:3000 |
| **API Swagger docs** | http://localhost:8000/docs |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:8889/metrics |
| OTel health | http://localhost:13133 |
| Kafka (external) | localhost:29092 |

---

## Interactive Demo

The dashboard uses a seeded demo user (`550e8400-e29b-41d4-a716-446655440000`).

1. **Chat** — every message is PII-scanned by Presidio; facts are extracted and stored in the RAG memory bank (the AI remembers you)
2. **Click "🚨 REVOKE DEMO'S CONSENT"** — triggers the full cascade with a GSAP animation
3. **Chat again** — PII is redacted, memory is frozen (AI replies but learns nothing new)
4. **Click "✅ RESTORE CONSENT"** — grants consent; backend auto-clears the freeze log
5. **Click "Reset Demo"** — wipes all memory, chat, and consent for a clean slate

---

## Quick API Demo

```bash
# Grant consent
curl -X POST http://localhost:8000/consent \
  -H "Content-Type: application/json" \
  -d '{"user_id":"550e8400-e29b-41d4-a716-446655440000","data_type":"pii","purpose":"model_training","status":"granted"}'

# Chat (memory is recorded)
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_id":"550e8400-e29b-41d4-a716-446655440000","message":"My name is Alice and I live in London"}'

# Revoke via webhook
curl -X POST http://localhost:8000/webhook/consent-revoke \
  -H "Content-Type: application/json" \
  -d '{"userId":"550e8400-e29b-41d4-a716-446655440000","purpose":"model_training","consentStatus":"revoked","timestamp":"2026-04-30T12:00:00Z"}'

# Inference is now blocked (403)
curl -X POST http://localhost:8000/infer/predict \
  -H "X-User-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"hello"}'

# Scan a third-party policy for consent bypass clauses
curl -X POST http://localhost:8000/policy/scan \
  -H "Content-Type: application/json" \
  -d '{"integration_name":"ExampleAI","policy_text":"We may use your data to train our models indefinitely."}'
```

---

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `POSTGRES_HOST` | PostgreSQL host | `localhost` | Yes |
| `POSTGRES_PORT` | PostgreSQL port | `5432` | Yes |
| `POSTGRES_DB` | Database name | `consentflow` | Yes |
| `POSTGRES_USER` | DB user | `consentflow` | Yes |
| `POSTGRES_PASSWORD` | DB password | `consentflow` | Yes |
| `REDIS_HOST` | Redis host | `localhost` | Yes |
| `REDIS_PORT` | Redis port | `6379` | Yes |
| `REDIS_DB` | Redis DB index | `0` | Yes |
| `REDIS_PASSWORD` | Redis auth | *(empty)* | No |
| `APP_ENV` | Environment label | `development` | Yes |
| `LOG_LEVEL` | Log verbosity | `INFO` | Yes |
| `CONSENT_CACHE_TTL` | Redis TTL (seconds) | `60` | Yes |
| `KAFKA_BROKER_URL` | Kafka broker | `localhost:29092` | Yes |
| `KAFKA_TOPIC_REVOKE` | Revocation topic | `consent.revoked` | Yes |
| `OTEL_ENABLED` | Enable OTel | `false` | No |
| `OTEL_ENDPOINT` | OTLP gRPC endpoint | `http://localhost:4317` | No |
| `OTEL_SERVICE_NAME` | OTel service name | `consentflow` | No |
| `GEMINI_API_KEY` | Google Gemini API key (AI Tier 2) | *(empty)* | Recommended |
| `MISTRAL_API_KEY` | Mistral API key (AI Tier 1) | *(empty)* | Recommended |
| `MISTRAL_MODEL` | Mistral model | `mistral-small-latest` | No |
| `OLLAMA_BASE_URL` | Ollama endpoint (local fallback) | `http://localhost:11434` | No |
| `OLLAMA_MODEL` | Ollama model | `gemma2:2b` | No |

> **AI fallback chain:** Chat and Policy Auditor use **Mistral → Gemini 2.0 Flash → Ollama**. Set at least one API key for production use.

---

## API Reference

Full interactive docs: **http://localhost:8000/docs**

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/users` | Register user (returns UUID) |
| `GET` | `/users` | List all users with consent summary |
| `GET` | `/users/{user_id}` | Get user by UUID |

### Consent
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/consent` | Upsert consent (granting auto-clears freeze log) |
| `GET` | `/consent` | List all records |
| `GET` | `/consent/{user_id}/{purpose}` | Effective status (Redis-cached) |
| `POST` | `/consent/revoke` | Revoke all rows for user+purpose |

### Webhook
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/webhook/consent-revoke` | OneTrust-style webhook — DB + Redis + Kafka + freeze log |
| `POST` | `/webhook` | Frontend alias |

### Chat (RAG)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat/message` | Send message; get AI reply + memory state |
| `GET` | `/chat/state/{user_id}` | Memory + freeze + consent state |
| `DELETE` | `/chat/state/{user_id}` | Full demo reset |
| `GET` | `/chat/history` | Paginated chat log |

### Pipeline Gates
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/infer/predict` | Protected inference (ASGI consent middleware) |
| `GET` | `/audit/trail` | Query audit log |
| `GET` | `/dashboard/stats` | Aggregated metrics |

### Policy Auditor
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/policy/scan` | LLM scan of third-party ToS |
| `GET` | `/policy/scans` | List past scans |
| `GET` | `/policy/scans/{scan_id}` | Get scan result |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Postgres + Redis + Kafka + OTel status |

---

## Database Schema (6 migrations)

| Migration | Table | Purpose |
|-----------|-------|---------|
| `001_init.sql` | `users`, `consent_records` | Core consent store |
| `002_audit_log.sql` | `audit_log` | Enforcement event log |
| `003_seed_demo_user.sql` | — | Seeds demo UUID |
| `004_policy_scans.sql` | `policy_scans` | Gate 05 LLM scan results |
| `005_chat_memory.sql` | `user_memory`, `chat_log` | RAG memory + chat history |
| `006_consent_freeze_log.sql` | `consent_freeze_log` | Memory freeze snapshot |

---

## Running Tests

```bash
cd consentflow-backend
uv run pytest                          # full suite
uv run pytest --cov=consentflow        # with coverage
uv run pytest tests/test_consent.py    # consent CRUD
uv run pytest tests/test_step4.py      # inference gate
uv run pytest tests/test_policy_auditor.py  # policy LLM logic
```

---

## Platform Notes — Apple Silicon

Add `platform: linux/amd64` to the `zookeeper` and `kafka` services in `docker-compose.yml`. All other images are multi-arch.

```yaml
zookeeper:
  image: confluentinc/cp-zookeeper:7.6.0
  platform: linux/amd64
kafka:
  image: confluentinc/cp-kafka:7.6.0
  platform: linux/amd64
```

---

## License

[MIT](LICENSE) © 2026 Rishu7011
