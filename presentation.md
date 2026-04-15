# ConsentFlow — Presentation

> **Real-time consent enforcement across your entire AI pipeline.**
> *GDPR/CCPA-compliant middleware for AI applications.*

---

## Slide 1 — The Problem

### Users trust AI apps with deeply personal data.

When a user revokes consent, the question is:
**Does the AI actually stop using their data?**

In most systems — no. The answer is:

- Inference still runs using their stored profile
- Training datasets still contain their PII
- Model weights still reflect their history
- Plugin integrations have no idea consent was revoked

**Consent revocation is a compliance checkbox. It should be a technical guarantee.**

---

## Slide 2 — What is ConsentFlow?

### Consent enforcement middleware for AI pipelines.

ConsentFlow is a full-stack system that:

1. Captures consent revocation from any source (CMP, UI, API, webhook)
2. Propagates it **instantly** through the entire AI stack
3. **Freezes** the user's memory bank — the AI stops learning from them
4. **Blocks** inference for revoked users — `403 Forbidden` in <5 ms
5. **Redacts** PII from all messages using Microsoft Presidio
6. **Quarantines** in-flight MLflow training runs via Kafka
7. **Audits** every enforcement action with full traceability

**One revocation. Every gate. Real time.**

---

## Slide 3 — Live Demo: What You See

### Three-panel interactive dashboard

```
┌─────────────────┬──────────────────────┬─────────────────┐
│   Memory Bank   │    ConsentFlow AI    │  Pipeline Gates │
│                 │                      │                 │
│  🟢 LEARNING    │  [Chat interface]    │ 🤖 Training     │
│                 │                      │    🟢 Learning  │
│  • User's name  │  Gemini AI with      │ 🛡 Presidio     │
│  • Location     │  RAG context from    │    🟢 Scanning  │
│  • Profession   │  memory bank         │ 🗄 Dataset      │
│  • Preferences  │                      │    🟢 Active    │
│                 │                      │ ⚡ Inference    │
│  3 facts known  │  [Enter message...]  │    🟢 Allowed   │
│                 │                      │ 📊 Drift        │
│  🛡 Presidio:   │  [  Send →  ]       │    🟢 Monitoring│
│  scanning msgs  │                      │ 📨 Kafka        │
└─────────────────┴──────────────────────┴─────────────────┘
       [  🚨 REVOKE DEMO'S CONSENT  ]
```

---

## Slide 4 — The Demo Flow

### Step 1 — Build a memory profile

Chat with the AI. Tell it your name, city, profession.

Every message:
- **Presidio scans** for 18 PII entity types (names, Aadhaar, PAN, phone, age, medical conditions, salary...)
- **Facts are extracted** using 50+ pattern rules and stored in the RAG knowledge base
- **The AI replies** using your profile as context — it remembers you

> *"My name is Alice, I live in London, I'm a software engineer."*
> → AI: "Nice to meet you, Alice! How can I help you today?"

---

### Step 2 — Revoke Consent

**Click: 🚨 REVOKE DEMO'S CONSENT**

Watch the cascade:

```
0.0s → Training Gate    🔴 FROZEN
0.1s → Memory Panel     border turns coral, FROZEN stamp appears
0.2s → Presidio         🔴 Blocking
0.4s → Dataset Gate     🔴 PII Scrubbed
0.5s → Redis Cache      invalidating…
0.6s → Kafka            🔴 Event fired (consent.revoked published)
0.7s → Redis Cache      🔴 Cleared
0.8s → Inference Gate   🔴 Blocked 403
1.0s → MLflow           🔴 Quarantined
1.2s → Drift Monitor    🔴 Flagged
1.4s → Toast: "✓ Kafka event fired  ✓ Redis cleared  ✓ 5 gates frozen"
```

**One click. 8 systems enforced. 1.4 seconds.**

---

### Step 3 — Chat After Revocation

The AI still responds — but watch what changed:

> *"My phone is 9876543210"*
> → **Message shown:** "My phone is `<REDACTED>`" (coral highlight)
> → **Memory panel:** "🔴 Memory blocked" — nothing new stored
> → **Memory bank:** dimmed to 45% opacity — frozen forever

The AI uses the same memory context it had at freeze time.
It responds helpfully — but it learns nothing new.

---

### Step 4 — Restore Consent

**Click: ✅ RESTORE CONSENT**

- `POST /consent` with `status: "granted"`
- Backend automatically clears the freeze log
- Memory bank unfreezes
- Chat history is preserved — the conversation continues seamlessly
- All gates return to 🟢 active state

---

### Step 5 — Policy Auditor

Paste any AI integration's Terms of Service URL or text.

The system:
1. Fetches and strips HTML (up to 12,000 characters)
2. Sends to LLM chain: **Gemini 2.0 Flash → Mistral → Ollama**
3. Scans for 7 categories of consent-bypass clauses
4. Returns structured risk report with GDPR/CCPA article references

**Example output:**
```json
{
  "overall_risk_level": "critical",
  "findings": [
    {
      "severity": "critical",
      "category": "Training on Inputs",
      "clause_excerpt": "We may use your conversations to train our models...",
      "article_reference": "GDPR Article 7(3)"
    }
  ]
}
```

---

## Slide 5 — Technical Architecture

### Backend Stack

| Component | Technology | Role |
|-----------|------------|------|
| API | FastAPI 0.115 (Python 3.12) | REST API, ASGI middleware |
| Database | PostgreSQL 16 + asyncpg | Authoritative consent store |
| Cache | Redis 7 | Sub-millisecond consent lookups |
| Event Bus | Apache Kafka | Real-time revocation propagation |
| PII Engine | Microsoft Presidio + spaCy | 18-entity detection + redaction |
| AI Tier 1 | Mistral (mistral-small-latest) | Primary LLM |
| AI Tier 2 | Google Gemini 2.0 Flash | First fallback |
| AI Tier 3 | Ollama (gemma2:2b) | Local offline fallback |
| ML Tracking | MLflow | Training run quarantine |
| Drift Monitor | Evidently AI | Consent-aware data drift |
| Observability | OpenTelemetry → Grafana | Distributed tracing + metrics |

### Frontend Stack

| Component | Technology |
|-----------|------------|
| Framework | Next.js 16.2, React 19, TypeScript |
| Animations | Framer Motion (state transitions) + GSAP (cascade timeline) |
| Styling | Tailwind CSS v4 + shadcn/ui + custom CSS tokens |
| HTTP | Axios with X-User-ID interceptor |
| State | React hooks + 2s/3s polling |
| Toasts | Sonner |

---

## Slide 6 — Enforcement Gates Deep Dive

### Gate 1: Training Gate (Memory Store)

**Before revocation:** Every user message → Presidio scan → fact extraction → stored in `user_memory` → injected into AI context on next message.

**After revocation:** `extract_and_store()` is never called. The AI context is permanently frozen at whatever was stored when consent was revoked. `consent_freeze_log` records the memory count at that exact moment.

### Gate 2: Presidio PII Redaction

Runs on **every message**, regardless of consent status.

When consent is revoked, the **redacted** message is what gets sent to the AI — names, phone numbers, Aadhaar, PAN, age, medical conditions, salary, relationship status are all replaced with `<REDACTED>`.

Custom India-specific recognizers: `IN_AADHAAR` (12-digit), `IN_PAN` (10-char), `IN_PHONE` (Indian mobile with +91), plus GDPR Article 9 sensitive categories.

### Gate 3: Inference Gate

ASGI `ConsentMiddleware` on the FastAPI app. Intercepts every request to `/infer/*` **before** the handler runs.

Consent lookup: Redis first (≤1 ms cache hit) → Postgres fallback → fail-closed (revoked if any error).

Returns `403 Forbidden` with no computation performed — the handler never executes.

### Gate 4: Dataset Gate

When preparing datasets for model training, `dataset_gate.py` checks consent per record. Revoked users' records are anonymized using Presidio before being logged to MLflow.

### Gate 5: Drift Monitor

`monitoring_gate.py` wraps Evidently AI. Tags each monitoring sample with `_consent_status`. Emits structured `DriftAlert` for revoked-user samples. Severity is graded: `warning` (<5 revoked samples) or `critical` (≥5).

### Gate 6: Policy Auditor

LLM-powered scanner for third-party AI integration ToS. Checks 7 categories of consent-bypass clauses. Uses Gemini → Mistral → Ollama fallback chain. Results stored in `policy_scans` with SHA-256 dedup key.

---

## Slide 7 — Database Design

### 6 migrations — 7 tables

```
migration 001 → users, consent_records
migration 002 → audit_log
migration 003 → seed demo user
migration 004 → policy_scans
migration 005 → user_memory, chat_log
migration 006 → consent_freeze_log
```

### Consent as State, Not Event

`consent_records` uses **upsert semantics** — one row per `(user_id, purpose, data_type)` triple, always reflecting the latest state. This optimizes the hot path: every gate lookup is a single-row read.

`audit_log` is **append-only** — an immutable record of every gate action with OTel `trace_id` for distributed tracing correlation.

### Freeze Log Pattern

`consent_freeze_log` is a one-row-per-user table. Written by `POST /webhook` with the memory count at freeze time. **Automatically deleted** by `POST /consent` when status is `granted`. This is what enables the restore flow to work without a separate "unfreeze" endpoint.

---

## Slide 8 — Revocation Propagation Timeline

```
T+0ms    User clicks "Revoke" in dashboard
T+5ms    POST /webhook received
T+10ms   PostgreSQL upsert complete (consent_records → revoked)
T+12ms   Redis cache invalidated
T+15ms   consent_freeze_log written (memory snapshot)
T+20ms   Kafka event published (consent.revoked)
T+21ms   HTTP 200 returned to frontend
T+22ms   Frontend cascade animation begins
T+1400ms All 8 UI gates showing frozen state
T+??ms   Training gate Kafka consumer picks up event → MLflow runs quarantined
```

From user click to database enforced: **~15 ms**.
Next inference request: **<5 ms** (Redis cache hit → 403).

---

## Slide 9 — Compliance Coverage

| Regulation | Requirement | ConsentFlow Implementation |
|------------|-------------|---------------------------|
| GDPR Art. 7(3) | Withdrawal of consent must be as easy as giving it | One-click revoke button; or API call |
| GDPR Art. 17 | Right to erasure | `DELETE /chat/state/{user_id}` clears all memory and chat history |
| GDPR Art. 22 | Automated decision-making | Inference gate blocks automated AI responses for revoked users |
| GDPR Art. 9 | Special category data | Presidio detects medical, financial, relationship status PII |
| CCPA 1798.120 | Right to opt out of sale | Consent purpose system supports multiple purposes including analytics |
| CCPA 1798.100 | Right to know | Audit trail provides complete record of all data processing actions |

---

## Slide 10 — Key Design Decisions

### Fail-Closed Semantics
When the consent check service fails (network error, DB down), the system defaults to **revoked**. No inference runs on ambiguous consent.

### Idempotent Webhook
The `POST /webhook/consent-revoke` endpoint uses `INSERT … ON CONFLICT`. Duplicate signals from CMP systems (like OneTrust) are completely safe.

### Memory Freeze vs. Memory Delete
On revocation, memories are **frozen, not deleted**. The AI still has context — it just stops learning. This is intentional: deleting memories would produce incoherent responses. The freeze is reversible; the user can restore consent and the AI resumes learning.

### Multi-Tier AI Fallback
The system never goes dark. If Mistral is down, Gemini takes over. If Gemini quota is exhausted, Ollama (local) serves as the final offline fallback. The fallback is automatic via LangChain's `with_fallbacks()`.

### Freeze Log Auto-Clear
Granting consent via `POST /consent` automatically deletes the freeze log entry in the **same transaction**. No separate "unfreeze" call needed. This keeps the frontend restore flow to a single API call.

---

## Slide 11 — What This Is Not

ConsentFlow is a **demonstration and reference implementation**. It shows:
- How consent enforcement should be architectured across an AI pipeline
- The technical patterns for PII detection, RAG memory management, and gate enforcement
- A working full-stack system you can run locally and extend

For production deployment, you would integrate these patterns with your existing:
- CMP (OneTrust, Osano, Cookiebot) — via the webhook endpoint
- ML platform (SageMaker, Vertex AI, Azure ML) — via the gate modules
- Identity provider — via the user management endpoints
- Data warehouse — via the dataset gate

---

## Quick Reference

**Demo user UUID:** `550e8400-e29b-41d4-a716-446655440000`

**Start the full stack:**
```bash
cd consentflow-backend && docker compose up --build
cd consentflow-frontend && npm install && npm run dev
```

**URLs:**
- Dashboard: http://localhost:3000
- API Docs: http://localhost:8000/docs

**Key endpoints:**
- `POST /webhook/consent-revoke` — trigger revocation
- `POST /consent` — grant/restore consent
- `POST /chat/message` — RAG chat
- `GET /chat/state/{user_id}` — memory state
- `POST /policy/scan` — ToS scanner
- `GET /audit/trail` — audit log

**AI keys needed:** `GEMINI_API_KEY`, `MISTRAL_API_KEY` (or just `OLLAMA_MODEL` for local-only)
