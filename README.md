# ConsentFlow

> **Real-time consent enforcement across your entire AI pipeline.**

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.2-black)](https://nextjs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

ConsentFlow is a full-stack middleware system that enforces user consent revocation across an AI pipeline in real time. When a user revokes consent, ConsentFlow propagates the revocation instantly — from API to cache to event bus — and freezes the RAG memory bank, blocks inference, scrubs datasets, and quarantines training runs.

---

## 🏗️ Architecture Overview

The system consists of three main components:

### 1. The Backend Core (FastAPI)
The backend intercepts data at various AI pipeline stages via **Enforcement Gates**:

| Gate | Layer | Enforcement |
|------|-------|-------------|
| **Gate 01: Dataset** | Data prep | Anonymizes revoked users' data before MLflow registration via Presidio |
| **Gate 02: Training** | Model training | Kafka consumer quarantines MLflow runs on revocation |
| **Gate 03: Inference** | Live serving | ASGI middleware returns `403` in <5 ms (Redis cache hit) |
| **Gate 04: Drift Monitor** | Monitoring | Flags revoked-user samples in Evidently drift windows |
| **Gate 05: Policy Auditor** | Compliance | LLM-based ToS scanner (Anthropic Claude) for third-party AI integrations |

### 2. The Frontend Dashboard (Next.js)
A Next.js 16 (App Router) interface providing a three-panel interactive dashboard:
- **Live RAG Memory Bank**: See facts extracted from chat history.
- **Real-Time AI Chat**: Chat interface with PII masking and RAG integration.
- **Pipeline Gates**: Animated view of the 5 gates with a live audit ticker.

### 3. The Privacy Shield (Chrome Extension)
A Manifest V3 browser extension (`consentflow-extension`) that masks your PII before it reaches any external AI chatbot (ChatGPT, Claude).
- **Interceptor**: Detects PII (Email, Phone, Aadhaar, PAN, UPI) in your chat input and replaces it with dummy values or tokens (e.g. `[PERSON_1]`).
- **Reverse Mapper**: Automatically restores the dummy tokens to real values in the AI's streaming response.
- **Offline Fallback**: Works entirely locally when the backend is unreachable.

---

## 🚀 Quick Start

### Prerequisites

- Docker + Docker Compose v2
- Node.js 20+ (for frontend and extension)
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
Starts PostgreSQL 16, Redis 7, Zookeeper, Kafka, the ConsentFlow API, OTel Collector, and Grafana. Migrations `001`–`006` are auto-applied at startup.

### 3. Start the Frontend Dashboard

```bash
cd ../consentflow-frontend
npm install
npm run dev
```
Open **http://localhost:3000** or **http://localhost:3001** (check your terminal).

### 4. Build and Load the Chrome Extension

The extension intercepts PII locally before it hits the AI platform. **You MUST build it first**.

```bash
cd ../consentflow-extension
npm install
npm run build
```

Then, in Chrome:
1. Go to `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked** and select the `consentflow-extension/dist` folder.

---

## 🎮 Interactive Demos

### Demo 1: Full Pipeline Revocation
The dashboard uses a seeded demo user (`550e8400-e29b-41d4-a716-446655440000`).
1. **Chat**: Send a message. PII is scanned; facts are extracted and stored in the RAG memory bank.
2. **Revoke Consent**: Click "🚨 REVOKE DEMO'S CONSENT" to trigger the full Kafka revocation cascade.
3. **Chat Again**: PII is redacted, memory is frozen (AI replies but learns nothing new). Inference checks will start returning 403 Forbidden.
4. **Restore Consent**: Click "✅ RESTORE CONSENT" to grant consent. Backend auto-clears the freeze log.

### Demo 2: Privacy Shield Extension
1. Open ChatGPT or Claude.
2. Type: "My name is Alex Smith and my phone number is 9999999999".
3. The extension instantly replaces these with tokens/dummies before sending to the AI.
4. When the AI responds, the tokens are seamlessly reversed in your browser.

---

## 🔌 API Reference

Full interactive docs: **http://localhost:8000/docs**

### Core Services
| Service | Internal URL | Description |
|---------|-------------|-------------|
| **Backend API** | `http://localhost:8000` | FastAPI server with `/consent`, `/infer`, `/policy/scan` |
| **Frontend** | `http://localhost:3000` | Next.js app |
| **Grafana** | `http://localhost:3001` | Observability dashboards |
| **Prometheus** | `http://localhost:8889/metrics` | Metrics |
| **OTel Health** | `http://localhost:13133` | OTel Collector |
| **Kafka** | `localhost:29092` | Event broker |

### Key API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/consent` | Upsert consent |
| `POST` | `/consent/revoke` | Revoke consent for user+purpose |
| `POST` | `/webhook/consent-revoke` | OneTrust-style webhook — DB + Redis + Kafka |
| `POST` | `/chat/message` | Send message; get AI reply + memory state |
| `POST` | `/infer/predict` | Protected inference (ASGI consent middleware) |
| `POST` | `/policy/scan` | LLM scan of third-party ToS |

---

## 🗄️ Database Schema

The system uses 6 core PostgreSQL migrations:
| Migration | Table | Purpose |
|-----------|-------|---------|
| `001_init.sql` | `users`, `consent_records` | Core consent store |
| `002_audit_log.sql` | `audit_log` | Enforcement event log |
| `003_seed_demo_user.sql` | — | Seeds demo UUID |
| `004_policy_scans.sql` | `policy_scans` | Gate 05 LLM scan results |
| `005_chat_memory.sql` | `user_memory`, `chat_log` | RAG memory + chat history |
| `006_consent_freeze_log.sql` | `consent_freeze_log` | Memory freeze snapshot |

---

## 🛠️ Testing

**Backend:**
```bash
cd consentflow-backend
uv run pytest                          # full suite
uv run pytest --cov=consentflow        # with coverage
uv run pytest tests/test_step4.py      # inference gate
uv run pytest tests/test_policy_auditor.py  # policy LLM logic
```

**Extension:**
```bash
cd consentflow-extension
npm test
```

---

## 📜 License

[MIT](LICENSE) © 2026 Rishu7011
