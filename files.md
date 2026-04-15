# ConsentFlow — File Reference

Complete annotated index of every file in the repository.

---

## Root

| File | Description |
|------|-------------|
| `README.md` | Primary project documentation — setup, architecture, API reference, database schema |
| `backend.md` | Detailed backend implementation reference |
| `frontend.md` | Detailed frontend implementation reference |
| `files.md` | This file — complete file index |
| `presentation.md` | Slide-deck narrative for demos and pitches |
| `plan.md` | Original development plan with all implementation steps |
| `project-summary.md` | High-level project overview and feature summary |
| `LICENSE` | MIT License |
| `.gitignore` | Git ignore rules (venv, .next, .env, __pycache__, etc.) |

---

## `consentflow-backend/`

### Root-level files

| File | Description |
|------|-------------|
| `.env` | Local environment variables (not committed) |
| `.env.example` | Template with all required variables and documentation |
| `.python-version` | Python version pin (`3.12.x`) for pyenv/uv |
| `pyproject.toml` | uv/hatch project config — version `0.3.0`, all Python dependencies, tool config (ruff, mypy, pytest) |
| `uv.lock` | Locked dependency tree for reproducible installs |
| `Dockerfile` | Multi-stage Docker image for the FastAPI app |
| `docker-compose.yml` | Full stack: PostgreSQL 16, Redis 7, Zookeeper, Kafka, App, OTel Collector, Grafana |
| `otel-collector-config.yaml` | OTel Collector pipeline: OTLP receiver → Prometheus exporter |
| `ConsentFlow_Postman_Collection.json` | Postman collection with all API endpoints pre-configured |
| `seed_db.py` | Standalone script to seed the demo user and sample consent records |
| `cleanup_db.py` | Standalone script to wipe all tables for a clean reset |
| `README.md` | Backend-specific quick-start note (defers to root README) |

---

### `consentflow/` (Python package)

| File | Size | Description |
|------|------|-------------|
| `__init__.py` | tiny | Package marker |
| `anonymizer.py` | 8 KB | **Presidio PII engine.** Singletons: `analyzer` (AnalyzerEngine, en_core_web_lg), `anonymizer` (AnonymizerEngine). Custom recognizers: `IN_AADHAAR`, `IN_PAN`, `IN_PHONE`, `AGE`, `MEDICAL_CONDITION`, `FINANCIAL_INFO`, `RELATIONSHIP_STATUS`, `PERSON` (demo names). `ALL_PII_ENTITIES` list (18 types). `anonymize_record()` for dataset gate. |
| `dataset_gate.py` | 7 KB | **Gate 01 — Dataset Gate.** Checks consent per record, anonymizes revoked users' PII using Presidio, logs MLflow metrics (`total_records`, `consented_count`, `anonymized_count`), saves cleaned dataset artifact. |
| `gemini_client.py` | 4 KB | **Multi-tier AI client.** Singleton `gemini_client`. LangChain chain: Mistral → Gemini 2.0 Flash → Ollama fallback. Injects user memories as bullet points into system prompt. Max 200 tokens. |
| `inference_gate.py` | 8 KB | **Gate 03 — Inference Gate.** `ConsentMiddleware(BaseHTTPMiddleware)`. Protects `/infer` prefix. Extracts user_id from `X-User-ID` header or JSON body. Fail-closed: missing user → 400, revoked → 403, service error → 503. |
| `langchain_gate.py` | 6 KB | **LangChain callback equivalent** of the inference gate. For use in LangChain pipelines that need consent enforcement at the callback level. |
| `memory_store.py` | 18 KB | **RAG knowledge base per user.** Singleton `memory_store`. 50+ regex patterns across 7 rule groups (identity, location, professional, health, relationship, financial, preference). `extract_and_store()` — fact extraction + dedup + persist. `get_memories()` — always returns frozen set after revocation. `clear_memories()` — full demo reset. `get_state()` — frontend polling response. |
| `mlflow_utils.py` | 10 KB | **MLflow helpers.** `get_or_create_experiment()`, `search_runs_by_user()`, `tag_run_quarantined()`, `get_run_consent_status()`. Used by dataset gate and training gate. |
| `monitoring_gate.py` | 16 KB | **Gate 04 — Drift Monitor.** Evidently AI wrapper. Tags each sample with `_consent_status`. Runs `DataDriftPreset`. Emits `DriftAlert` for revoked-user samples. Severity: `warning` (<5 revoked) or `critical` (≥5). Returns `DriftCheckResult`. |
| `otel_dataset_gate.py` | 6 KB | OTel-instrumented wrapper for `dataset_gate.py`. Emits `dataset_gate.check` span with standard attributes. Appends `audit_log` row. |
| `otel_inference_gate.py` | 4 KB | OTel-instrumented wrapper for inference gate operations. |
| `otel_monitoring_gate.py` | 7 KB | OTel-instrumented wrapper for `monitoring_gate.py`. Emits `monitoring_gate.check` span. |
| `otel_training_gate.py` | 4 KB | OTel-instrumented wrapper for `training_gate.py`. Emits `training_gate.quarantine` span. |
| `policy_auditor.py` | 21 KB | **Gate 05 — Policy Auditor.** `PolicyAuditor` class + `analyze_policy()` + `fetch_policy_text()` helpers. Fetches HTML policy docs, strips tags, truncates to 12,000 chars, SHA-256 hashes. LangChain chain: Gemini → Mistral → Ollama. Validates/recomputes severity. Persists to `policy_scans` + `audit_log`. 7 scanning categories, 4 severity levels. |
| `sdk.py` | 6 KB | **Thin consent SDK.** `is_user_consented(user_id, purpose, redis_client, db_pool)` — Redis-first lookup, Postgres fallback, fail-closed default. Used by `ConsentMiddleware` and `dataset_gate`. |
| `telemetry.py` | 3 KB | **OTel bootstrap.** `configure_otel(endpoint, service_name)` — sets up OTLP gRPC exporter, BatchSpanProcessor, resource attributes. Called at lifespan startup when `otel_enabled=True`. |
| `training_gate.py` | 13 KB | **Gate 02 — Training Gate.** Kafka consumer `TrainingGateConsumer`. Consumes `consent.revoked` events. Calls `search_runs_by_user()` + `tag_run_quarantined()` on each affected MLflow run. Records `QuarantineRecord`. Standalone: `python -m consentflow.training_gate`. |

---

### `consentflow/app/`

| File | Size | Description |
|------|------|-------------|
| `__init__.py` | tiny | Package marker |
| `cache.py` | 4 KB | Redis cache helpers. `get_consent_cache()`, `set_consent_cache()`, `invalidate_consent_cache()`. Key pattern: `consent:{user_id}:{purpose}`. TTL from `settings.consent_cache_ttl`. |
| `config.py` | 3 KB | `Settings(BaseSettings)` — reads `.env`. Provides all configuration including Gemini, Mistral, Ollama, OTel, Kafka, Postgres, Redis settings. Computed properties: `postgres_dsn`, `asyncpg_dsn`, `redis_url`. |
| `db.py` | 1 KB | asyncpg pool factory. `create_pool()`, `close_pool()`, `check_postgres()` (ping). |
| `kafka_producer.py` | 5 KB | aiokafka producer factory. `create_kafka_producer()`, `close_kafka_producer()`, `publish_revocation(producer, user_id, purpose, timestamp)`. Topic: `consent.revoked`. |
| `main.py` | 8 KB | **FastAPI app factory.** `create_app()` — registers all routers and middlewares. `lifespan()` — startup (Postgres → migrations → Redis → Kafka) and shutdown (reverse order). Health endpoint (`GET /health`). CORS: `localhost:3000`, `localhost:3001`. ConsentMiddleware on `/infer`. |
| `models.py` | 7 KB | All Pydantic v2 models. `ConsentUpsertRequest`, `ConsentRevokeRequest`, `UserCreateRequest`, `ConsentRecord`, `ConsentStatusResponse`, `UserRecord`, `UserListRecord`, `HealthResponse`, `AuditLogEntry`, `AuditTrailResponse`, `PolicyFinding`, `PolicyScanRequest`, `PolicyScanResult`, `PolicyScanListItem`. |

---

### `consentflow/app/routers/`

| File | Size | Prefix | Key Endpoints |
|------|------|--------|---------------|
| `__init__.py` | tiny | — | Package marker |
| `audit.py` | 5 KB | `/audit` | `GET /audit/trail` — query audit_log with user_id, gate_name, limit filters |
| `chat.py` | 16 KB | `/chat` | `POST /chat/message`, `GET /chat/state/{user_id}`, `DELETE /chat/state/{user_id}`, `GET /chat/history` |
| `consent.py` | 9 KB | `/consent` | `GET /consent`, `POST /consent` (with auto-unfreeze), `POST /consent/revoke`, `GET /consent/{user_id}/{purpose}` |
| `dashboard.py` | 4 KB | `/dashboard` | `GET /dashboard/stats` — users, granted, blocked, purposes, 24h sparkline, policy scan counts |
| `infer.py` | 1 KB | `/infer` | `POST /infer/predict` — dummy protected endpoint behind `ConsentMiddleware` |
| `policy.py` | 9 KB | `/policy` | `POST /policy/scan`, `GET /policy/scans`, `GET /policy/scans/{scan_id}` |
| `users.py` | 7 KB | `/users` | `POST /users` (201), `GET /users` (with consent summary), `GET /users/{user_id}` |
| `webhook.py` | 10 KB | `/webhook` | `POST /webhook/consent-revoke` — OneTrust-style; DB upsert + Redis invalidate + Kafka publish + freeze log write |

---

### `consentflow/migrations/`

| File | Description |
|------|-------------|
| `001_init.sql` | Creates `users` and `consent_records` tables with indexes and constraints |
| `002_audit_log.sql` | Creates `audit_log` table with indexes on `user_id`, `event_time DESC`, `gate_name` |
| `003_seed_demo_user.sql` | Inserts demo user `550e8400-e29b-41d4-a716-446655440000` (alice@demo.consentflow.io) |
| `004_policy_scans.sql` | Creates `policy_scans` table for Gate 05 LLM scan results |
| `005_chat_memory.sql` | Creates `user_memory` (RAG facts) and `chat_log` (conversation history) tables |
| `006_consent_freeze_log.sql` | Creates `consent_freeze_log` table (PK: user_id) to snapshot memory count at revocation time |

All migrations are auto-applied in sorted order at app startup via the lifespan handler. Safe to re-run (all use `CREATE TABLE IF NOT EXISTS`).

---

### `tests/`

| File | What it covers |
|------|----------------|
| `test_health.py` | `GET /health` smoke test — Postgres + Redis + Kafka + OTel fields |
| `test_consent.py` | Consent CRUD (upsert, revoke, status lookup), Redis cache behavior, 404 on unknown user |
| `test_step3.py` | Dataset gate — granted records pass unchanged, revoked records anonymized; MLflow metrics |
| `test_step4.py` | Inference gate ASGI middleware — allow, block (403), missing user (400), fail-closed (503) |
| `test_step5.py` | Training gate Kafka consumer + `mlflow_utils` quarantine tag flow |
| `test_monitoring_gate.py` | Drift monitor — alert emission, severity thresholds, empty window, all-granted window |
| `test_step7.py` | OTel wrapper span attributes + `GET /audit/trail` response shape |
| `test_policy_auditor.py` | Policy auditor — LLM parsing, severity validation, overall_risk recompute, HTML strip |
| `test_gate05_e2e.py` | Full Gate 05 API + DB pipeline with mocked Ollama/Gemini responses |

---

### `grafana/`

| File | Description |
|------|-------------|
| `dashboards/` | Provisioned Grafana dashboard JSON (uid: `consentflow-observability`) |
| `datasources/` | Prometheus datasource provisioning YAML |

Grafana is accessible at `http://localhost:3001` with anonymous access (no login required in development).

---

## `consentflow-frontend/`

### Root-level files

| File | Description |
|------|-------------|
| `package.json` | npm project — Next.js 16.2.4, React 19, Framer Motion, GSAP, Axios, TanStack Query, shadcn/ui, Sonner |
| `package-lock.json` | Locked npm dependency tree |
| `next.config.ts` | Next.js config (minimal — no special rewrites needed) |
| `tsconfig.json` | TypeScript config with path alias `@/*` → project root |
| `postcss.config.mjs` | PostCSS config for Tailwind CSS v4 |
| `components.json` | shadcn/ui registry config |
| `eslint.config.mjs` | ESLint config (Next.js defaults) |
| `AGENTS.md` | Agent instructions for AI-assisted development |
| `CLAUDE.md` | Claude-specific dev notes |
| `.gitignore` | Ignores `.next`, `node_modules`, `.env.local` |

---

### `app/`

| File | Description |
|------|-------------|
| `layout.tsx` | Root layout — Inter font, `Providers` wrapper, dark background |
| `page.tsx` | **Main demo dashboard** — `DemoPage` component, 352 lines. All state, polling, and event handlers. Three-column grid layout: MemoryPanel, ChatPanel, PipelinePanel. Top bar with consent status indicator. Bottom Revoke/Restore button (Framer Motion AnimatePresence). Audit ticker. |
| `globals.css` | Design tokens (`--cf-*` CSS custom properties), global resets, custom animations (`.pulse-coral`, `.glow-teal`, `.pulse-border-coral`) |
| `favicon.ico` | ConsentFlow favicon |

---

### `app/api/` — Next.js API Route Proxies

Each route proxies requests to the FastAPI backend at `NEXT_PUBLIC_API_URL`.

| Route file | Proxies to |
|-----------|-----------|
| `audit/route.ts` | `GET /audit/trail` |
| `chat/route.ts` | `POST /chat/message`, `GET /chat/state/*`, `DELETE /chat/state/*`, `GET /chat/history` |
| `consent/route.ts` | `POST /consent` |
| `dashboard-stats/route.ts` | `GET /dashboard/stats` |
| `health/route.ts` | `GET /health` |
| `infer/route.ts` | `POST /infer/predict` |
| `policy/route.ts` | `POST /policy/scan`, `GET /policy/scans` |
| `users/route.ts` | `GET /users` |
| `webhook/route.ts` | `POST /webhook/consent-revoke` |

---

### `components/`

| File | Description |
|------|-------------|
| `Sidebar.tsx` | Navigation sidebar component (optional, currently not rendered in main demo) |
| `providers.tsx` | `Providers` wrapper — TanStack Query `QueryClientProvider`, theme context |

#### `components/demo/`

| File | Size | Description |
|------|------|-------------|
| `ChatPanel.tsx` | 9 KB | Center panel. Message history (user + AI bubbles). PII redaction highlighting with `<mark>` elements. XSS-safe `dangerouslySetInnerHTML` with prior HTML escape. Typing indicator (3-dot bounce). Chat input with Enter-key send. |
| `MemoryPanel.tsx` | 6 KB | Left panel. "FROZEN" stamp overlay (AnimatePresence spring). Memory chips with PII-category color badges. Freeze count display. PII shield row. Border color transitions. |
| `PipelinePanel.tsx` | 7 KB | Right panel. 5 animated gate rows (GATES config) + Kafka + MLflow + Redis rows. Per-gate AnimatePresence badge transitions. Kafka "consent.revoked published" animated text. Redis "invalidating…" intermediate state. |

#### `components/ui/`

shadcn/ui component library (Badge, Button, Input, etc.) — auto-generated, not manually edited.

---

### `lib/`

| File | Size | Description |
|------|------|-------------|
| `axios.ts` | <1 KB | Axios instance with base URL + request interceptor that attaches `X-User-ID` header from `sessionStorage` |
| `constants.ts` | <1 KB | `API_BASE_URL` constant from `process.env.NEXT_PUBLIC_API_URL` |
| `types.ts` | 2 KB | All TypeScript interfaces: `MemoryState`, `ChatMessage`, `ChatResponse`, `AuditEntry`, `HealthStatus`, `DashboardStats`, `User`, `ConsentRecord`, `PolicyFinding`, `PolicyScanResult`, `PolicyScanListItem` |
| `utils.ts` | 2 KB | `GATE_COLORS` (audit ticker badge colors), `PII_ICONS` (memory chip icons), `PII_COLORS` (memory chip colors), `timeAgo()` (relative timestamp), `cn()` (Tailwind class merger) |

---

### `public/`

Static assets served by Next.js. Currently contains project branding assets.

---

## Key File Relationships

```
page.tsx
  ├── uses: lib/axios.ts (API calls)
  ├── uses: lib/types.ts (state types)
  ├── uses: lib/utils.ts (GATE_COLORS, timeAgo)
  ├── renders: components/demo/MemoryPanel.tsx
  │              uses: lib/utils.ts (PII_ICONS, PII_COLORS)
  ├── renders: components/demo/ChatPanel.tsx
  │              uses: lib/utils.ts (timeAgo)
  └── renders: components/demo/PipelinePanel.tsx

consentflow/app/main.py
  ├── imports: consentflow/inference_gate.py (ConsentMiddleware)
  ├── imports: consentflow/app/routers/*.py (all routers)
  ├── imports: consentflow/app/cache.py
  ├── imports: consentflow/app/db.py
  └── imports: consentflow/app/kafka_producer.py

consentflow/app/routers/chat.py
  ├── imports: consentflow/anonymizer.py (analyzer, anonymizer, ALL_PII_ENTITIES)
  ├── imports: consentflow/gemini_client.py (gemini_client)
  └── imports: consentflow/memory_store.py (memory_store)

consentflow/app/routers/webhook.py
  └── imports: consentflow/memory_store.py (memory_store.get_memory_count)

consentflow/policy_auditor.py
  └── imports: langchain-google-genai, langchain-mistralai, langchain-ollama
```
