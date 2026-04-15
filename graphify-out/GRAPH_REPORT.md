# Graph Report - ConsentFlow  (2026-05-05)

## Corpus Check
- 119 files · ~68,928 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 820 nodes · 1258 edges · 48 communities detected
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 144 edges (avg confidence: 0.77)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `15119c01`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]

## God Nodes (most connected - your core abstractions)
1. `str` - 25 edges
2. `BaseModel` - 25 edges
3. `TrainingGateConsumer` - 20 edges
4. `cn()` - 15 edges
5. `FakeKafkaConsumer` - 14 edges
6. `PolicyAuditor` - 13 edges
7. `QuarantineRecord` - 12 edges
8. `ConsentAwareDriftMonitor` - 11 edges
9. `FakeKafkaMessage` - 11 edges
10. `is_user_consented()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Gate 05 Policy Auditor with Claude` --semantically_similar_to--> `Policy Auditor`  [INFERRED] [semantically similar]
  project-summary.md → README.md
- `Pipeline Panel` --references--> `Inference Gate`  [INFERRED]
  frontend.md → README.md
- `Policy Auditor` --conceptually_related_to--> `Multi-Tier AI Client`  [INFERRED]
  README.md → backend.md
- `Backend Frontend Rebuild Strategy` --rationale_for--> `Chat Router`  [EXTRACTED]
  plan.md → backend.md
- `OpenTelemetry Observability` --references--> `OTel Collector Service`  [INFERRED]
  backend.md → consentflow-backend/docker-compose.yml

## Hyperedges (group relationships)
- **Consent Revocation Enforcement Flow** — backend_webhook_router, readme_kafka_revocation, backend_freeze_log [EXTRACTED 1.00]
- **Frontend Demo Tri-Panel** — frontend_memory_panel, frontend_chat_panel, frontend_pipeline_panel [EXTRACTED 1.00]
- **Observability Infrastructure Stack** — compose_otel_collector_service, compose_grafana_service, grafana_prometheus_datasource [EXTRACTED 1.00]

## Communities (72 total, 14 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (63): AuditLogEntry, AuditTrailResponse, ConsentRevokeRequest, ConsentStatusResponse, ConsentUpsertRequest, ExtensionAnonymizePlaceholderRequest, HealthResponse, PolicyFinding (+55 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (15): cn(), timeAgo(), Badge(), Dialog(), DialogTrigger(), ScrollArea(), Sheet(), SheetTrigger() (+7 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (22): GET(), getBackendUrl(), handleMessage(), buildHeaders(), DELETE(), GET(), POST(), GET() (+14 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (31): _parse_event(), QuarantineRecord, consentflow/training_gate.py — Kafka consumer that enforces consent at training, Handle a single revocation event for *user_id*.          Steps         -----, Continuously consume ``consent.revoked`` events until cancelled.          This, Create a real ``AIOKafkaConsumer`` and run the training gate loop.      Import, An immutable record of one quarantine action.      Attributes     ----------, Asynchronous Kafka consumer that quarantines MLflow runs on consent revocation. (+23 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (34): check_redis(), close_redis_client(), _consent_key(), create_redis_client(), get_consent_cache(), invalidate_consent_cache(), cache.py — Redis helpers for consent lookup caching.  Key schema:  consent:{us, Delete the cached consent entry for user+purpose. (+26 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (33): main(), consentflow/otel_inference_gate.py — OTel-instrumented inference gate helper (St, Insert one row into ``audit_log``.  Errors are logged, never raised., Record an OTel span and audit log row for one inference gate decision.      Pa, traced_inference_check(), _write_audit_row(), consentflow/otel_monitoring_gate.py — OTel-instrumented monitoring gate wrapper, Insert one row into ``audit_log``.  Errors are logged, never raised. (+25 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (28): analyze_policy(), _compute_max_severity(), fetch_policy_text(), PolicyAnalysisError, PolicyAuditor, PolicyFetchError, consentflow/policy_auditor.py — Gate 05: Policy Auditor  Fetches and analyses, Return plain text extracted from an HTML document. (+20 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (29): ConsentAwareDriftMonitor, DriftAlert, DriftCheckResult, consentflow/monitoring_gate.py — Consent-aware Evidently drift monitor (Step 6)., Wraps Evidently's DataDriftPreset with per-sample consent-status tagging., Add a ``_consent_status`` column (``"granted"`` / ``"revoked"``) to *df*., Run an Evidently ``DataDriftPreset`` report on *current_df* vs *reference_df*., Inspect ``_consent_status`` and emit one :class:`DriftAlert` per unique (+21 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (28): _cache_get(), _cache_invalidate(), _cache_set(), _cached_memories(), _extract_facts(), _extract_facts_from_clause(), _fingerprint(), _is_noisy_catchall() (+20 more)

### Community 9 - "Community 9"
Cohesion: 0.11
Nodes (29): PolicyScanRequest, Payload for POST /policy-auditor/scan — supply a URL, raw text, or both., _make_auditor(), _make_ollama_response(), _mock_ollama_client(), tests/test_gate05_e2e.py — Gate 05 (Policy Auditor) end-to-end smoke tests.  T, End-to-end scan pipeline in URL mode.      Mocks:     - httpx.AsyncClient.get, End-to-end scan in paste-text (no URL fetch) mode.      Mocks: Ollama → 0 find (+21 more)

### Community 10 - "Community 10"
Cohesion: 0.1
Nodes (19): attachAndBind(), loadConsentProfile(), main(), applyOfflineFallback(), attachInterceptor(), interceptClick(), sendToServiceWorker(), timeout() (+11 more)

### Community 11 - "Community 11"
Cohesion: 0.12
Nodes (25): fake_pool(), fake_redis(), fake_settings(), _make_auditor(), _make_ollama_response(), tests/test_policy_auditor.py — Gate 05: Policy Auditor unit test suite.  All t, LLM returns empty findings array → overall_risk_level must be 'low'., LLM wraps JSON in ```json ... ``` — must still parse correctly. (+17 more)

### Community 12 - "Community 12"
Cohesion: 0.1
Nodes (11): client(), fake_pool(), fake_redis(), FakeConnection, FakePool, FakeRedis, tests/conftest.py — shared pytest fixtures for ConsentFlow.  Strategy: overrid, Minimal asyncpg connection stub. (+3 more)

### Community 13 - "Community 13"
Cohesion: 0.13
Nodes (18): apply_quarantine_tags(), apply_quarantine_to_registered_model(), list_quarantined_runs(), _make_client(), consentflow/mlflow_utils.py — MLflow helper utilities for the Training Gate., Apply quarantine tags to an MLflow *run*.      Tags applied     ------------, Apply quarantine tags to a *registered model version*.      Parameters     --, Return all MLflow runs that have been flagged as quarantined.      Parameters (+10 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (18): anonymize_record(), _anonymize_text(), _anonymize_value(), consentflow/anonymizer.py — Full Presidio PII detection + anonymisation.  Plan, Return a copy of *record* with all string-valued PII fields masked.      Non-s, Recursively anonymize a value (dict, list, str, or other)., Detect and mask PII in a single text string.      Returns the anonymized strin, filtered_count() (+10 more)

### Community 15 - "Community 15"
Cohesion: 0.13
Nodes (17): BaseHTTPMiddleware, ConsentMiddleware, _extract_user_id(), consentflow/inference_gate.py — FastAPI middleware for inference-time consent en, Intercept the request, enforce consent, then forward or reject., ASGI middleware that enforces inference-time consent.      Parameters     ---, Return True iff *path* falls under a protected prefix., _check_postgres() (+9 more)

### Community 16 - "Community 16"
Cohesion: 0.13
Nodes (15): consentflow/otel_dataset_gate.py — OTel-instrumented dataset gate wrapper (Step, Insert one row into ``audit_log``.  Errors are logged, never raised., OTel-instrumented wrapper around ``register_dataset_with_consent_check``., traced_register_dataset(), _write_audit_row(), consentflow/otel_training_gate.py — OTel-instrumented training gate helper (Step, Record an OTel span and audit log row for a training gate quarantine event., Insert one row into ``audit_log``.  Errors are logged, never raised. (+7 more)

### Community 17 - "Community 17"
Cohesion: 0.17
Nodes (17): close_kafka_producer(), create_kafka_producer(), publish_revocation(), kafka_producer.py — Async Kafka producer for consent-revocation events.  Lifec, Instantiate and start an AIOKafkaProducer.      The producer serialises values, Flush pending messages and stop the producer., Publish a ``consent.revoked`` event to Kafka.      Parameters     ----------, _apply_revocation_to_db() (+9 more)

### Community 18 - "Community 18"
Cohesion: 0.18
Nodes (9): BaseCallbackHandler, ConsentCallbackHandler, ConsentRevokedException, consentflow/langchain_gate.py — LangChain callback handler for consent enforceme, Perform the consent check and raise if revoked., Called before every LLM invocation in synchronous chains., Called before every LLM invocation in async chains., Raised when a LangChain LLM call is attempted for a user whose consent     has (+1 more)

### Community 19 - "Community 19"
Cohesion: 0.17
Nodes (13): Consent Router, Consent Freeze Log, Webhook Router, Frontend API Proxy Routes, Consent Revocation Demo Narrative, ConsentFlow, FastAPI Backend, Kafka Revocation Event (+5 more)

### Community 20 - "Community 20"
Cohesion: 0.15
Nodes (13): Presidio Anonymizer Module, Audit Log, Chat Router, Multi-Tier AI Client, Memory Store, Chat Panel, Frontend Demo Page, Memory Panel (+5 more)

### Community 21 - "Community 21"
Cohesion: 0.23
Nodes (11): anonymize(), consent_profile(), _cors(), _generate_dummy(), options_handler(), extension.py — FastAPI router for the ConsentFlow Privacy Shield browser extensi, Handle pre-flight CORS requests from the browser extension., Swap placeholder tokens for random dummy values.      Input:  { "entity_refs": [ (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.25
Nodes (9): mock_is_user_consented(), tests/test_step4.py — Integration tests for Step 4 (Inference Gate).  Tests th, Patch the sdk.is_user_consented function so we do not actually     hit the data, Scenario 3: Missing user_id block., Scenario 2: User with revoked consent is blocked., Scenario 1: User with valid consent passes through., test_inference_gate_missing_user_id(), test_inference_gate_revoked_consent() (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.25
Nodes (11): OpenTelemetry Observability, ConsentFlow App Service, Backend Docker Compose Stack, Grafana Service, Kafka Service, OTel Collector Service, Postgres Service, Redis Service (+3 more)

### Community 24 - "Community 24"
Cohesion: 0.39
Nodes (7): tests/test_consent.py — Unit tests for /consent endpoints.  Uses in-memory fak, test_get_consent_cache_hit(), test_get_consent_cache_miss(), test_get_consent_not_found(), test_revoke_consent(), test_revoke_consent_not_found(), test_upsert_consent()

### Community 25 - "Community 25"
Cohesion: 0.43
Nodes (5): asyncpg_dsn(), postgres_dsn(), redis_url(), Settings, BaseSettings

### Community 26 - "Community 26"
Cohesion: 0.33
Nodes (4): GeminiClient, consentflow/gemini_client.py — Async Gemini 2.0 Flash LangChain client.  Refac, Async wrapper using LangChain for the Gemini generateContent REST endpoint., Build a context-aware prompt using LangChain and get a reply.          Tier 1:

### Community 27 - "Community 27"
Cohesion: 0.7
Nodes (3): DashboardStatsResponse, get_dashboard_stats(), _get_pool()

### Community 28 - "Community 28"
Cohesion: 0.5
Nodes (3): predict_model(), routers/infer.py — Dummy inference endpoints for testing the ConsentMiddleware., Dummy endpoint representing an AI model inference call.      This route sits b

### Community 31 - "Community 31"
Cohesion: 0.67
Nodes (4): Frontend Public Brand Asset, Monochrome Black Vector Style, Next.js Framework Brand, Next.js Wordmark Logo

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (3): Document File Icon, Folded Corner Indicator, Text Content Lines

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (3): Circular World Boundary, Globe Earth Icon, Latitude and Longitude Grid

### Community 35 - "Community 35"
Cohesion: 0.67
Nodes (3): Inverted Triangle Shape, Minimal Brand Identity, Vercel Logo Mark

### Community 36 - "Community 36"
Cohesion: 0.67
Nodes (3): Application Frame Outline, Browser Window Icon, Title Bar Control Dots

## Knowledge Gaps
- **220 isolated node(s):** `consentflow/anonymizer.py — Full Presidio PII detection + anonymisation.  Plan`, `Return a copy of *record* with all string-valued PII fields masked.      Non-s`, `Recursively anonymize a value (dict, list, str, or other).`, `Detect and mask PII in a single text string.      Returns the anonymized strin`, `Summary of a single dataset registration run.` (+215 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `str` connect `Community 5` to `Community 0`, `Community 3`, `Community 4`, `Community 6`, `Community 7`, `Community 13`, `Community 14`, `Community 15`, `Community 17`, `Community 18`, `Community 21`?**
  _High betweenness centrality (0.337) - this node is a cross-community bridge._
- **Why does `chat_message()` connect `Community 0` to `Community 8`, `Community 4`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Why does `FakeRedis` connect `Community 12` to `Community 8`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `str` (e.g. with `main()` and `register_dataset_with_consent_check()`) actually correct?**
  _`str` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `TrainingGateConsumer` (e.g. with `test_kafka_event_triggers_quarantine()` and `test_quarantine_tags_are_correct()`) actually correct?**
  _`TrainingGateConsumer` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `FakeKafkaConsumer` (e.g. with `QuarantineRecord` and `TrainingGateConsumer`) actually correct?**
  _`FakeKafkaConsumer` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `consentflow/anonymizer.py — Full Presidio PII detection + anonymisation.  Plan`, `Return a copy of *record* with all string-valued PII fields masked.      Non-s`, `Recursively anonymize a value (dict, list, str, or other).` to the rest of the system?**
  _220 weakly-connected nodes found - possible documentation gaps or missing edges._