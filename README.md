<div align="center">
  <img src="consentflow-extension/public/icons/icon.svg" alt="ConsentFlow Logo" width="120"/>
</div>

# ConsentFlow

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Next.js](https://img.shields.io/badge/Next.js-16.2-black)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Active-success)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

> **Real-time consent enforcement across your entire AI pipeline.**

```
   ██████╗ ██████╗ ███╗   ██╗███████╗███████╗███╗   ██╗████████╗
  ██╔════╝██╔═══██╗████╗  ██║██╔════╝██╔════╝████╗  ██║╚══██╔══╝
  ██║     ██║   ██║██╔██╗ ██║███████╗█████╗  ██╔██╗ ██║   ██║
  ██║     ██║   ██║██║╚██╗██║╚════██║██╔══╝  ██║╚██╗██║   ██║
  ╚██████╗╚██████╔╝██║ ╚████║███████║███████╗██║ ╚████║   ██║
   ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝

  ███████╗██╗      ██████╗ ██╗    ██╗
  ██╔════╝██║     ██╔═══██╗██║    ██║
  █████╗  ██║     ██║   ██║██║ █╗ ██║
  ██╔══╝  ██║     ██║   ██║██║███╗██║
  ██║     ███████╗╚██████╔╝╚███╔███╔╝
  ╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝
```

---

## 📋 Table of Contents

1. [The Problem](#-the-problem)
2. [The Solution](#-the-solution)
3. [Architecture Overview](#-architecture-overview)
4. [Enforcement Gates](#-enforcement-gates)
5. [Frontend Dashboard](#-frontend-dashboard)
6. [Privacy Shield Extension](#-privacy-shield-extension)
7. [Quick Start](#-quick-start)
8. [Interactive Demos](#-interactive-demos)
9. [API Reference](#-api-reference)
10. [Database Schema](#-database-schema)
11. [Testing](#-testing)
12. [License](#-license)

---

## 😤 The Problem

A user revokes their consent on your platform. You update a checkbox in a database. And then what?

- The **RAG memory bank** still holds their personal facts
- The **model training run** still includes their data
- The **inference endpoint** still serves their information
- The **drift monitor** still evaluates on their samples
- Third-party AI integrations quietly **continue processing their data**

Consent revocation is treated as a form field — not a system-wide event. The data keeps flowing. The model keeps learning. The user is legally unprotected.

This is the problem **ConsentFlow** was built to solve.

---

## 💡 The Solution

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                                                                                │
│  User Revokes Consent  ──▶  ConsentFlow  ──▶  Kafka Event Bus                 │
│                                                                                │
│  Kafka  ──▶  Gate 01: Dataset     ──▶  Anonymize via Presidio                 │
│         ──▶  Gate 02: Training    ──▶  Quarantine MLflow run                  │
│         ──▶  Gate 03: Inference   ──▶  Block in < 5 ms (Redis)                │
│         ──▶  Gate 04: Drift       ──▶  Flag revoked-user samples              │
│         ──▶  Gate 05: Policy      ──▶  LLM scan of third-party ToS            │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**ConsentFlow** is a full-stack middleware system that:

1. **Intercepts consent revocations** via webhook, API, or dashboard — and fans them out instantly across your entire AI pipeline
2. **Enforces at every layer** — dataset prep, model training, live inference, monitoring, and third-party integrations
3. **Freezes the RAG memory bank** so the AI stops learning from revoked users
4. **Blocks inference in < 5 ms** via a Redis-backed ASGI middleware gate
5. **Audits third-party ToS** using an LLM-based policy scanner (Claude) so you know exactly what downstream tools do with user data
6. **Masks PII in-browser** via a Chrome extension before data ever reaches any AI platform

No manual scrubbing. No delayed propagation. Everything is real-time.

---

## 🏗️ Architecture Overview

The system consists of three main components:

```
┌───────────────────────────────────────────────────────────────────────┐
│                         ConsentFlow System                            │
│                                                                       │
│  ┌────────────────────┐    ┌─────────────────────┐    ┌────────────┐  │
│  │  Backend Core       │    │  Frontend Dashboard  │    │  Chrome    │  │
│  │  (FastAPI)          │    │  (Next.js 16)        │    │  Extension │  │
│  │                    │    │                     │    │            │  │
│  │  • 5 Enforcement   │◀───│  • Live RAG Bank     │    │  • PII     │  │
│  │    Gates           │    │  • Real-time Chat    │    │    Masking │  │
│  │  • Kafka Events    │    │  • Pipeline View     │    │  • Token   │  │
│  │  • Redis Cache     │    │  • Audit Ticker      │    │    Reversal│  │
│  │  • PostgreSQL      │    │                     │    │            │  │
│  └────────────────────┘    └─────────────────────┘    └────────────┘  │
│           │                                                           │
│  ┌────────▼───────────────────────────────────────────────────────┐   │
│  │  Infrastructure: PostgreSQL · Redis · Kafka · Zookeeper        │   │
│  │  Observability:  OpenTelemetry · Prometheus · Grafana          │   │
│  └────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 🚧 Enforcement Gates

The backend intercepts data at five distinct AI pipeline stages. Each gate enforces consent in a fundamentally different way.

### Gate 01 — Dataset Layer

**What it does:** Anonymizes revoked users' data before it's registered in MLflow.

**How:** Runs Microsoft Presidio over raw dataset samples. Replaces PII (names, emails, phone numbers, Aadhaar, PAN) with typed tokens. The sanitized dataset gets registered; the original is discarded.

**Result:** Even if a training run starts immediately after a revocation, the revoked user's real data never makes it into the model weights.

---

### Gate 02 — Training Layer

**What it does:** Quarantines active MLflow training runs when a revocation arrives mid-training.

**How:** A Kafka consumer listens for `consent.revoked` events. When one arrives, it tags the corresponding MLflow run as quarantined and halts further logging. Downstream consumers are notified.

**Result:** No half-trained model accidentally learns from data the user has revoked.

---

### Gate 03 — Inference Layer

**What it does:** Returns `403 Forbidden` to any inference request for a revoked user, in under 5 ms.

**How:** An ASGI middleware layer checks a Redis cache on every `/infer/predict` request. Redis holds a bloom filter of revoked user IDs. Cache hit = instant block. Cache miss = DB fallback + cache warm.

**Result:** The model cannot be queried on behalf of a revoked user — even if the revocation just happened.

---

### Gate 04 — Drift Monitor Layer

**What it does:** Flags revoked-user data samples inside Evidently drift monitoring windows.

**How:** Before each drift evaluation batch, a pre-processor filters out samples belonging to revoked users and marks them in the audit log. Evidently never sees their data.

**Result:** Model drift reports are not contaminated by — and do not expose — revoked users' data.

---

### Gate 05 — Policy Auditor Layer

**What it does:** Uses an LLM (Anthropic Claude) to scan the Terms of Service of any third-party AI integration your pipeline connects to.

**How:** You submit a ToS URL or raw text to `/policy/scan`. Claude extracts clauses related to data retention, training use, and sharing. Results are stored in PostgreSQL and surfaced in the dashboard.

**Result:** You know — with audit trail — exactly what every downstream AI tool claims to do with user data, flagged against your consent policies.

---

## 🖥️ Frontend Dashboard

A Next.js 16 (App Router) three-panel interface:

| Panel | What you see |
|---|---|
| **Live RAG Memory Bank** | Facts extracted from a user's chat history in real time |
| **Real-Time AI Chat** | Chat interface with PII masking and RAG integration |
| **Pipeline Gates** | Animated live view of all 5 gates + a scrolling audit event ticker |

The dashboard uses a seeded demo user so you can trigger the full revocation cascade without any setup.

---

## 🔒 Privacy Shield Extension

A Manifest V3 Chrome extension that masks PII **before it leaves your browser** — before any AI platform ever sees it.

### How it works

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  You type: "My name is Alex and my Aadhaar is 1234 5678 9012"       │
│                         │                                            │
│                         ▼                                            │
│          ┌──────────────────────────────┐                            │
│          │  PII Interceptor             │                            │
│          │  Detects: Name, Aadhaar,     │                            │
│          │  Phone, PAN, UPI, Email      │                            │
│          └──────────────┬───────────────┘                            │
│                         │                                            │
│  Sent to AI: "My name is [PERSON_1] and my Aadhaar is [ID_1]"       │
│                         │                                            │
│                         ▼                                            │
│          ┌──────────────────────────────┐                            │
│          │  Reverse Mapper              │                            │
│          │  Restores tokens in the      │                            │
│          │  AI's streaming response     │                            │
│          └──────────────────────────────┘                            │
│                                                                      │
│  You read: "Hello Alex, your Aadhaar ending in 9012..."             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Supported PII types:** Email · Phone · Aadhaar · PAN · UPI · Named persons

**Works on:** ChatGPT · Claude · any AI chat interface

**Offline fallback:** Operates entirely locally when the ConsentFlow backend is unreachable.

---

## 🚀 Quick Start

### Prerequisites

- Docker + Docker Compose v2
- Node.js 20+
- Python 3.12+ and `uv` (for local backend dev only)

### 1. Clone and Configure

```bash
git clone https://github.com/Rishu7011/ConsentFlow.git
cd ConsentFlow/consentflow-backend
cp .env.example .env          # Linux/Mac
copy .env.example .env        # Windows
```

Edit `.env`. At minimum set `GEMINI_API_KEY` or `MISTRAL_API_KEY` for AI chat.

> **Apple Silicon users:** Add `platform: linux/amd64` to the `zookeeper` and `kafka` services in `docker-compose.yml`.

### 2. Start the Backend Stack

```bash
cd consentflow-backend
docker compose up --build
```

This starts PostgreSQL 16, Redis 7, Zookeeper, Kafka, the ConsentFlow API, OTel Collector, and Grafana. Migrations `001`–`006` are auto-applied at startup.

### 3. Start the Frontend Dashboard

```bash
cd ../consentflow-frontend
npm install
npm run dev
```

Open **http://localhost:3000** (or **:3001** — check your terminal).

### 4. Build and Load the Chrome Extension

```bash
cd ../consentflow-extension
npm install
npm run build
```

Then in Chrome:
1. Go to `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked** and select the `consentflow-extension/dist` folder

---

## 🎮 Interactive Demos

### Demo 1 — Full Pipeline Revocation

The dashboard uses a seeded demo user (`550e8400-e29b-41d4-a716-446655440000`).

1. **Chat** — Send a message. PII is scanned; facts are extracted and stored in the RAG memory bank.
2. **Revoke** — Click **🚨 REVOKE DEMO'S CONSENT** to trigger the full Kafka revocation cascade.
3. **Chat again** — PII is redacted, memory is frozen (the AI replies but learns nothing new). Inference returns `403 Forbidden`.
4. **Restore** — Click **✅ RESTORE CONSENT** to re-grant access. The backend auto-clears the freeze log.

Watch the **Pipeline Gates** panel animate through each enforcement stage in real time.

---

### Demo 2 — Privacy Shield Extension

1. Open ChatGPT or Claude in Chrome.
2. Type: *"My name is Alex Smith and my phone number is 9999999999"*
3. The extension instantly replaces these with tokens before the message is sent.
4. When the AI responds, the tokens are seamlessly reversed back in your browser.

The AI never sees your real data. You never notice the difference.

---

## 🔌 API Reference

Full interactive docs: **http://localhost:8000/docs**

### Core Services

| Service | URL | Description |
|---------|-----|-------------|
| **Backend API** | `http://localhost:8000` | FastAPI — `/consent`, `/infer`, `/policy/scan` |
| **Frontend** | `http://localhost:3000` | Next.js dashboard |
| **Grafana** | `http://localhost:3001` | Observability dashboards |
| **Prometheus** | `http://localhost:8889/metrics` | Metrics |
| **OTel Health** | `http://localhost:13133` | OTel Collector health |
| **Kafka** | `localhost:29092` | Event broker |

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/consent` | Upsert consent record |
| `POST` | `/consent/revoke` | Revoke consent for a user + purpose |
| `POST` | `/webhook/consent-revoke` | OneTrust-style webhook — DB + Redis + Kafka |
| `POST` | `/chat/message` | Send message; get AI reply + memory state |
| `POST` | `/infer/predict` | Protected inference (Gate 03 ASGI middleware) |
| `POST` | `/policy/scan` | LLM scan of a third-party ToS document |

---

## 🗄️ Database Schema

Six PostgreSQL migrations applied automatically at startup:

| Migration | Table(s) | Purpose |
|-----------|----------|---------|
| `001_init.sql` | `users`, `consent_records` | Core consent store |
| `002_audit_log.sql` | `audit_log` | Full enforcement event log |
| `003_seed_demo_user.sql` | — | Seeds the dashboard demo UUID |
| `004_policy_scans.sql` | `policy_scans` | Gate 05 LLM scan results |
| `005_chat_memory.sql` | `user_memory`, `chat_log` | RAG memory + chat history |
| `006_consent_freeze_log.sql` | `consent_freeze_log` | Memory freeze snapshot on revocation |

---

## 🛠️ Testing

**Backend:**

```bash
cd consentflow-backend

uv run pytest                                    # full suite
uv run pytest --cov=consentflow                  # with coverage report
uv run pytest tests/test_step4.py                # Gate 03: inference enforcement
uv run pytest tests/test_policy_auditor.py       # Gate 05: LLM policy scanner
```

**Extension:**

```bash
cd consentflow-extension
npm test
```

---

## 🗺️ Roadmap

### v1.1.0 — Coming Soon
- [ ] Gate 03 latency dashboard widget (p50 / p95 / p99 Redis hit times)
- [ ] Per-user consent history timeline in the dashboard
- [ ] Webhook retry queue with exponential backoff

### v1.2.0
- [ ] Multi-tenant support — enforce consent across isolated tenant namespaces
- [ ] Gate 05 continuous monitoring — re-scan third-party ToS on a schedule
- [ ] Slack / PagerDuty alerts on revocation cascade failures

### v2.0.0 — Future Vision
- [ ] OpenDP integration for differentially private dataset scrubbing
- [ ] Federated consent propagation across partner systems
- [ ] GDPR Article 17 auto-report generation
- [ ] Firefox extension support

---

## 📜 License

[MIT](LICENSE) © 2026 Rishu7011

---

<div align="center">

Built with 🛡️ and urgency by a developer who believes consent revocation should mean something.

**When a user says stop — everything stops.**

</div>
