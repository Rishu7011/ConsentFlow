# Graph Report - .  (2026-05-04)

## Corpus Check
- 125 files · ~62,230 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 718 nodes · 972 edges · 50 communities detected
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 136 edges (avg confidence: 0.77)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Tsx Badge|Tsx Badge]]
- [[_COMMUNITY_Otel Gate|Otel Gate]]
- [[_COMMUNITY_Dataset Anonymize|Dataset Anonymize]]
- [[_COMMUNITY_Policy Text|Policy Text]]
- [[_COMMUNITY_Training Gate|Training Gate]]
- [[_COMMUNITY_Memory Cache|Memory Cache]]
- [[_COMMUNITY_Get Post|Get Post]]
- [[_COMMUNITY_Producer Pool|Producer Pool]]
- [[_COMMUNITY_Scan Policy|Scan Policy]]
- [[_COMMUNITY_Init Stub|Init Stub]]
- [[_COMMUNITY_Runs Tags|Runs Tags]]
- [[_COMMUNITY_Policy Analyze|Policy Analyze]]
- [[_COMMUNITY_Chat Get|Chat Get]]
- [[_COMMUNITY_Consent Drift|Consent Drift]]
- [[_COMMUNITY_Dataframe Monitor|Dataframe Monitor]]
- [[_COMMUNITY_Consent Get|Consent Get]]
- [[_COMMUNITY_Policy Scan|Policy Scan]]
- [[_COMMUNITY_Consent Redis|Consent Redis]]
- [[_COMMUNITY_Consent Payload|Consent Payload]]
- [[_COMMUNITY_Consent Router|Consent Router]]
- [[_COMMUNITY_Panel Chat|Panel Chat]]
- [[_COMMUNITY_Inference Consent|Inference Consent]]
- [[_COMMUNITY_Grafana Otel|Grafana Otel]]
- [[_COMMUNITY_Get Users|Get Users]]
- [[_COMMUNITY_Inference Gate|Inference Gate]]
- [[_COMMUNITY_Audit Get|Audit Get]]
- [[_COMMUNITY_Consent Get|Consent Get]]
- [[_COMMUNITY_Gemini Client|Gemini Client]]
- [[_COMMUNITY_Dsn Asyncpg|Dsn Asyncpg]]
- [[_COMMUNITY_Dashboard Get|Dashboard Get]]
- [[_COMMUNITY_Infer Model|Infer Model]]
- [[_COMMUNITY_Providers Tsx|Providers Tsx]]
- [[_COMMUNITY_Brand Next|Brand Next]]
- [[_COMMUNITY_Health Tests|Health Tests]]
- [[_COMMUNITY_Document File|Document File]]
- [[_COMMUNITY_Circular World|Circular World]]
- [[_COMMUNITY_Inverted Triangle|Inverted Triangle]]
- [[_COMMUNITY_Application Frame|Application Frame]]
- [[_COMMUNITY_Alias Number|Alias Number]]
- [[_COMMUNITY_Try Resolve|Try Resolve]]
- [[_COMMUNITY_Deserialise Kafka|Deserialise Kafka]]
- [[_COMMUNITY_Scenario Kafka|Scenario Kafka]]
- [[_COMMUNITY_Scenario Verify|Scenario Verify]]
- [[_COMMUNITY_Scenario Verify|Scenario Verify]]
- [[_COMMUNITY_Mlflow Has|Mlflow Has]]
- [[_COMMUNITY_Malformed Event|Malformed Event]]
- [[_COMMUNITY_Aiokafkaconsumer Can|Aiokafkaconsumer Can]]
- [[_COMMUNITY_Set Mlflow|Set Mlflow]]
- [[_COMMUNITY_Dataset Gate|Dataset Gate]]
- [[_COMMUNITY_Drift Monitor|Drift Monitor]]

## God Nodes (most connected - your core abstractions)
1. `TrainingGateConsumer` - 19 edges
2. `cn()` - 15 edges
3. `FakeKafkaConsumer` - 13 edges
4. `PolicyAuditor` - 12 edges
5. `QuarantineRecord` - 11 edges
6. `ConsentAwareDriftMonitor` - 10 edges
7. `FakeKafkaMessage` - 10 edges
8. `is_user_consented()` - 9 edges
9. `lifespan()` - 9 edges
10. `receive_consent_revoke()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Gate 05 Policy Auditor with Claude` --semantically_similar_to--> `Policy Auditor`  [INFERRED] [semantically similar]
  project-summary.md → README.md
- `lifespan()` --calls--> `close_redis_client()`  [INFERRED]
  consentflow-backend/consentflow/app/main.py → consentflow-backend/consentflow/app/cache.py
- `Pipeline Panel` --references--> `Inference Gate`  [INFERRED]
  frontend.md → README.md
- `Policy Auditor` --conceptually_related_to--> `Multi-Tier AI Client`  [INFERRED]
  README.md → backend.md
- `Backend Frontend Rebuild Strategy` --rationale_for--> `Chat Router`  [EXTRACTED]
  plan.md → backend.md

## Hyperedges (group relationships)
- **Consent Revocation Enforcement Flow** — backend_webhook_router, readme_kafka_revocation, backend_freeze_log [EXTRACTED 1.00]
- **Frontend Demo Tri-Panel** — frontend_memory_panel, frontend_chat_panel, frontend_pipeline_panel [EXTRACTED 1.00]
- **Observability Infrastructure Stack** — compose_otel_collector_service, compose_grafana_service, grafana_prometheus_datasource [EXTRACTED 1.00]

## Communities (66 total, 17 thin omitted)

### Community 0 - "Tsx Badge"
Cohesion: 0.06
Nodes (13): cn(), timeAgo(), Badge(), Dialog(), DialogTrigger(), ScrollArea(), Sheet(), SheetTrigger() (+5 more)

### Community 1 - "Otel Gate"
Cohesion: 0.05
Nodes (45): consentflow/otel_dataset_gate.py — OTel-instrumented dataset gate wrapper (Step, Insert one row into ``audit_log``.  Errors are logged, never raised., OTel-instrumented wrapper around ``register_dataset_with_consent_check``., traced_register_dataset(), _write_audit_row(), consentflow/otel_inference_gate.py — OTel-instrumented inference gate helper (St, Insert one row into ``audit_log``.  Errors are logged, never raised., Record an OTel span and audit log row for one inference gate decision.      Pa (+37 more)

### Community 2 - "Dataset Anonymize"
Cohesion: 0.05
Nodes (36): BaseCallbackHandler, anonymize_record(), _anonymize_text(), _anonymize_value(), consentflow/anonymizer.py — Full Presidio PII detection + anonymisation.  Plan 1, Return a copy of *record* with all string-valued PII fields masked.      Non-str, Recursively anonymize a value (dict, list, str, or other)., Detect and mask PII in a single text string.      Returns the anonymized string. (+28 more)

### Community 3 - "Policy Text"
Cohesion: 0.06
Nodes (29): analyze_policy(), _compute_max_severity(), fetch_policy_text(), PolicyAnalysisError, PolicyAuditor, PolicyFetchError, consentflow/policy_auditor.py — Gate 05: Policy Auditor  Fetches and analyses, Return plain text extracted from an HTML document. (+21 more)

### Community 4 - "Training Gate"
Cohesion: 0.1
Nodes (30): _parse_event(), QuarantineRecord, consentflow/training_gate.py — Kafka consumer that enforces consent at training, Handle a single revocation event for *user_id*.          Steps         -----, Continuously consume ``consent.revoked`` events until cancelled.          This, Create a real ``AIOKafkaConsumer`` and run the training gate loop.      Import, An immutable record of one quarantine action.      Attributes     ----------, Asynchronous Kafka consumer that quarantines MLflow runs on consent revocation. (+22 more)

### Community 5 - "Memory Cache"
Cohesion: 0.08
Nodes (28): _cache_get(), _cache_invalidate(), _cache_set(), _cached_memories(), _extract_facts(), _extract_facts_from_clause(), _fingerprint(), _is_noisy_catchall() (+20 more)

### Community 6 - "Get Post"
Cohesion: 0.08
Nodes (19): GET(), buildHeaders(), DELETE(), GET(), POST(), GET(), GET(), GET() (+11 more)

### Community 7 - "Producer Pool"
Cohesion: 0.07
Nodes (28): create_redis_client(), check_postgres(), close_pool(), create_pool(), db.py — asyncpg connection pool management.  The pool is stored on the FastAPI, Create and return an asyncpg connection pool., Gracefully close all connections in the pool., Ping Postgres; return 'ok' or error string. (+20 more)

### Community 8 - "Scan Policy"
Cohesion: 0.08
Nodes (29): PolicyScanRequest, Payload for POST /policy-auditor/scan — supply a URL, raw text, or both., _make_auditor(), _make_ollama_response(), _mock_ollama_client(), tests/test_gate05_e2e.py — Gate 05 (Policy Auditor) end-to-end smoke tests.  T, End-to-end scan pipeline in URL mode.      Mocks:     - httpx.AsyncClient.get, End-to-end scan in paste-text (no URL fetch) mode.      Mocks: Ollama → 0 find (+21 more)

### Community 9 - "Init Stub"
Cohesion: 0.09
Nodes (11): client(), fake_pool(), fake_redis(), FakeConnection, FakePool, FakeRedis, tests/conftest.py — shared pytest fixtures for ConsentFlow.  Strategy: overrid, Minimal asyncpg connection stub. (+3 more)

### Community 10 - "Runs Tags"
Cohesion: 0.12
Nodes (18): apply_quarantine_tags(), apply_quarantine_to_registered_model(), list_quarantined_runs(), _make_client(), consentflow/mlflow_utils.py — MLflow helper utilities for the Training Gate., Apply quarantine tags to an MLflow *run*.      Tags applied     ------------, Apply quarantine tags to a *registered model version*.      Parameters     --, Return all MLflow runs that have been flagged as quarantined.      Parameters (+10 more)

### Community 11 - "Policy Analyze"
Cohesion: 0.09
Nodes (21): fake_settings(), _make_ollama_response(), tests/test_policy_auditor.py — Gate 05: Policy Auditor unit test suite.  All t, LLM returns empty findings array → overall_risk_level must be 'low'., LLM wraps JSON in ```json ... ``` — must still parse correctly., LLM returns plain text instead of JSON → ValueError must propagate., LLM returns severity='banana' → must be coerced to 'low'., HTTP 200 from a fake URL → returns the plain text body. (+13 more)

### Community 12 - "Chat Get"
Cohesion: 0.18
Nodes (17): BaseModel, chat_message(), ChatHistoryEntry, ChatHistoryResponse, ChatRequest, ChatResetResponse, ChatResponse, ChatStateResponse (+9 more)

### Community 13 - "Consent Drift"
Cohesion: 0.13
Nodes (12): ConsentAwareDriftMonitor, DriftAlert, DriftCheckResult, consentflow/monitoring_gate.py — Consent-aware Evidently drift monitor (Step 6)., Wraps Evidently's DataDriftPreset with per-sample consent-status tagging., Add a ``_consent_status`` column (``"granted"`` / ``"revoked"``) to *df*., Run an Evidently ``DataDriftPreset`` report on *current_df* vs *reference_df*., Inspect ``_consent_status`` and emit one :class:`DriftAlert` per unique (+4 more)

### Community 14 - "Dataframe Monitor"
Cohesion: 0.17
Nodes (17): _fake_consent_fn(), _make_monitor(), _make_reference_df(), tests/test_monitoring_gate.py — Unit tests for Step 6 (Drift Monitor Integration, SCENARIO 2     ----------     Current window has 3 rows from USER_REVOKED_1 an, SCENARIO 3     ----------     6 rows from USER_REVOKED_1 → severity == ``"crit, EDGE CASE 1     -----------     A DataFrame that has no 'user_id' column must, EDGE CASE 2     -----------     An empty current DataFrame (0 rows, correct co (+9 more)

### Community 15 - "Consent Get"
Cohesion: 0.17
Nodes (12): invalidate_consent_cache(), Delete the cached consent entry for user+purpose., ConsentRecord, ConsentStatus, Full consent record returned from the DB., main(), Enum, list_consents() (+4 more)

### Community 16 - "Policy Scan"
Cohesion: 0.18
Nodes (15): PolicyFinding, PolicyScanResult, A single red-flag finding extracted from a policy document., Full scan result returned from POST /policy-auditor/scan., get_policy_scan(), _get_pool(), _get_redis(), list_policy_scans() (+7 more)

### Community 17 - "Consent Redis"
Cohesion: 0.21
Nodes (12): check_redis(), close_redis_client(), _consent_key(), get_consent_cache(), cache.py — Redis helpers for consent lookup caching.  Key schema:  consent:{us, Ping Redis; return 'ok' or an error string., Return the cached consent payload as a dict, or None on cache miss., Store the consent payload in Redis with TTL.     `payload` must be JSON-seriali (+4 more)

### Community 18 - "Consent Payload"
Cohesion: 0.15
Nodes (11): ConsentRevokeRequest, ConsentStatusResponse, ConsentUpsertRequest, HealthResponse, PolicyScanListItem, Lightweight row returned from GET /policy-auditor/scans (list view)., Payload for POST /consent — grant or revoke a consent record., Payload for POST /consent/revoke. (+3 more)

### Community 19 - "Consent Router"
Cohesion: 0.17
Nodes (13): Consent Router, Consent Freeze Log, Webhook Router, Frontend API Proxy Routes, Consent Revocation Demo Narrative, ConsentFlow, FastAPI Backend, Kafka Revocation Event (+5 more)

### Community 20 - "Panel Chat"
Cohesion: 0.15
Nodes (13): Presidio Anonymizer Module, Audit Log, Chat Router, Multi-Tier AI Client, Memory Store, Chat Panel, Frontend Demo Page, Memory Panel (+5 more)

### Community 21 - "Inference Consent"
Cohesion: 0.22
Nodes (7): BaseHTTPMiddleware, ConsentMiddleware, _extract_user_id(), consentflow/inference_gate.py — FastAPI middleware for inference-time consent en, Intercept the request, enforce consent, then forward or reject., ASGI middleware that enforces inference-time consent.      Parameters     ---, Return True iff *path* falls under a protected prefix.

### Community 22 - "Grafana Otel"
Cohesion: 0.25
Nodes (11): OpenTelemetry Observability, ConsentFlow App Service, Backend Docker Compose Stack, Grafana Service, Kafka Service, OTel Collector Service, Postgres Service, Redis Service (+3 more)

### Community 23 - "Get Users"
Cohesion: 0.24
Nodes (8): Enriched user record returned from GET /users, includes consent summary., UserListRecord, UserRecord, _create_user(), get_user(), list_users(), routers/users.py — User management endpoints.  Endpoints --------- GET    /u, register_user()

### Community 24 - "Inference Gate"
Cohesion: 0.2
Nodes (9): mock_is_user_consented(), tests/test_step4.py — Integration tests for Step 4 (Inference Gate).  Tests th, Patch the sdk.is_user_consented function so we do not actually     hit the data, Scenario 3: Missing user_id block., Scenario 2: User with revoked consent is blocked., Scenario 1: User with valid consent passes through., test_inference_gate_missing_user_id(), test_inference_gate_revoked_consent() (+1 more)

### Community 25 - "Audit Get"
Cohesion: 0.22
Nodes (7): AuditLogEntry, AuditTrailResponse, A single row from the audit_log table., Response envelope for GET /audit/trail., get_audit_trail(), routers/audit.py — Audit trail endpoint (Step 7).  Endpoint -------- GET /au, Return time-ordered consent audit trail with optional filters.

### Community 27 - "Gemini Client"
Cohesion: 0.33
Nodes (4): GeminiClient, consentflow/gemini_client.py — Async Gemini 2.0 Flash LangChain client.  Refacto, Async wrapper using LangChain for the Gemini generateContent REST endpoint., Build a context-aware prompt using LangChain and get a reply.          Tier 1: M

### Community 30 - "Infer Model"
Cohesion: 0.5
Nodes (3): predict_model(), routers/infer.py — Dummy inference endpoints for testing the ConsentMiddleware., Dummy endpoint representing an AI model inference call.      This route sits b

### Community 32 - "Brand Next"
Cohesion: 0.67
Nodes (4): Frontend Public Brand Asset, Monochrome Black Vector Style, Next.js Framework Brand, Next.js Wordmark Logo

### Community 34 - "Document File"
Cohesion: 1.0
Nodes (3): Document File Icon, Folded Corner Indicator, Text Content Lines

### Community 35 - "Circular World"
Cohesion: 1.0
Nodes (3): Circular World Boundary, Globe Earth Icon, Latitude and Longitude Grid

### Community 36 - "Inverted Triangle"
Cohesion: 0.67
Nodes (3): Inverted Triangle Shape, Minimal Brand Identity, Vercel Logo Mark

### Community 37 - "Application Frame"
Cohesion: 0.67
Nodes (3): Application Frame Outline, Browser Window Icon, Title Bar Control Dots

## Knowledge Gaps
- **240 isolated node(s):** `consentflow/anonymizer.py — Full Presidio PII detection + anonymisation.  Plan 1`, `Return a copy of *record* with all string-valued PII fields masked.      Non-str`, `Recursively anonymize a value (dict, list, str, or other).`, `Detect and mask PII in a single text string.      Returns the anonymized string.`, `consentflow/dataset_gate.py — Consent-aware dataset registration gate.  Public` (+235 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `chat_message()` connect `Chat Get` to `Consent Redis`, `Memory Cache`?**
  _High betweenness centrality (0.165) - this node is a cross-community bridge._
- **Why does `FakeRedis` connect `Init Stub` to `Memory Cache`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Why does `get_chat_history()` connect `Chat Get` to `Consent Get`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Are the 23 inferred relationships involving `str` (e.g. with `main()` and `register_dataset_with_consent_check()`) actually correct?**
  _`str` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `TrainingGateConsumer` (e.g. with `FakeKafkaMessage` and `FakeKafkaConsumer`) actually correct?**
  _`TrainingGateConsumer` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `FakeKafkaConsumer` (e.g. with `QuarantineRecord` and `TrainingGateConsumer`) actually correct?**
  _`FakeKafkaConsumer` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `consentflow/anonymizer.py — Full Presidio PII detection + anonymisation.  Plan 1`, `Return a copy of *record* with all string-valued PII fields masked.      Non-str`, `Recursively anonymize a value (dict, list, str, or other).` to the rest of the system?**
  _240 weakly-connected nodes found - possible documentation gaps or missing edges._