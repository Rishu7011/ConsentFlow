# Contributing to ConsentFlow

Thank you for your interest in contributing! ConsentFlow is a GSSoC 2026 project — all skill levels are welcome, from documentation fixes to new enforcement gates.

Please read this guide before opening an issue or submitting a PR.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Project Structure](#project-structure)
3. [Setting Up Locally](#setting-up-locally)
4. [Branch Naming](#branch-naming)
5. [Commit Messages](#commit-messages)
6. [Code Style](#code-style)
7. [Running Tests](#running-tests)
8. [Submitting a Pull Request](#submitting-a-pull-request)
9. [Issue Labels](#issue-labels)
10. [Getting Help](#getting-help)

---

## Code of Conduct

Be respectful. Harassment, discrimination, or hostile behaviour of any kind will not be tolerated. This project follows the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

---

## Project Structure

```
ConsentFlow/
├── consentflow-backend/     # FastAPI · Python 3.12 · asyncpg · Redis · Kafka
├── consentflow-frontend/    # Next.js 16 · React 19 · TypeScript · Tailwind v4
├── consentflow-extension/   # Chrome Extension · Manifest V3 · TypeScript
├── CONTRIBUTING.md          # This file
└── README.md
```

Each sub-project has its own reference doc:
- [`backend.md`](./backend.md) — full backend module reference
- [`frontend.md`](./frontend.md) — full frontend component reference

---

## Setting Up Locally

### Prerequisites

| Tool | Minimum version |
|------|----------------|
| Docker + Docker Compose | v2 |
| Node.js | 20+ |
| Python | 3.12+ |
| `uv` (Python package manager) | latest |

### 1 — Fork and clone

1. Click **Fork** on the top right of the [ConsentFlow repo](https://github.com/Rishu7011/ConsentFlow)
2. Clone your fork locally:

```bash
git clone https://github.com/<your-username>/ConsentFlow.git
cd ConsentFlow
```

3. Add the upstream remote so you can stay in sync:

```bash
git remote add upstream https://github.com/Rishu7011/ConsentFlow.git
```

### 2 — Backend

> Before starting, make sure Docker Desktop is running.

```bash
cd consentflow-backend

# Copy env file and set at least one AI key
cp .env.example .env      # Linux/Mac
copy .env.example .env    # Windows

# Start full infrastructure stack (Postgres, Redis, Kafka, API, Grafana)
docker compose up --build
```

> **Apple Silicon:** Add `platform: linux/amd64` to the `zookeeper` and `kafka` services in `docker-compose.yml`.

For local backend dev without Docker:

```bash
cd consentflow-backend
uv sync
uv run python -m spacy download en_core_web_lg
uv run uvicorn consentflow.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3 — Frontend

```bash
cd consentflow-frontend
npm install
npm run dev        # → http://localhost:3000 (or :3001 if 3000 is taken)
```

### 4 — Chrome Extension

```bash
cd consentflow-extension
npm install
npm run build
```

Then in Chrome → `chrome://extensions/` → Enable **Developer mode** → **Load unpacked** → select `consentflow-extension/dist/`.

---

## Branch Naming

Use the following prefixes — keep names short and lowercase:

| Prefix | When to use | Example |
|--------|-------------|---------|
| `feat/` | New feature or enhancement | `feat/consent-history-timeline` |
| `fix/` | Bug fix | `fix/redis-ttl-stale-grant` |
| `docs/` | Documentation only | `docs/add-contributing-guide` |
| `chore/` | Build, CI, tooling, deps | `chore/add-github-actions-ci` |
| `test/` | Adding or fixing tests only | `test/inference-gate-unit` |
| `refactor/` | Code restructure, no behavior change | `refactor/memory-store-dedup` |

Always branch off `main`:

```bash
git checkout main
git pull origin main
git checkout -b feat/your-feature-name
```

---

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer — e.g. Closes #42]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `perf`

**Scopes:** `backend`, `frontend`, `extension`, `ci`, `db`, `deps`

Examples:

```
feat(backend): add pagination to GET /consent endpoint

fix(frontend): correct frozen state source of truth after page refresh

docs(backend): document CORS allowed_origins env variable

Closes #17
```

Keep the summary line under 72 characters. Use the body for *why*, not *what*.

---

## Code Style

### Python (Backend)

- Formatter: **`ruff format`** (configured in `pyproject.toml`)
- Linter: **`ruff check`**
- Type hints required on all public functions
- Async functions (`async def`) for all route handlers and DB calls
- No bare `except:` — always catch specific exceptions

Run before committing:

```bash
cd consentflow-backend
uv run ruff format .
uv run ruff check .
```

### TypeScript (Frontend & Extension)

- Linter: **ESLint** — frontend uses `eslint-config-next`; run with `npm run lint`
- No Prettier config exists yet — formatting is not enforced automatically
- All new components must be typed — no `any`
- Use `"use client"` only where strictly necessary (Next.js App Router)

Run before committing:

```bash
# Frontend
cd consentflow-frontend
npm run lint

# Extension — no lint script configured yet; type-check manually if needed
cd consentflow-extension
npx tsc --noEmit
```

---

## Running Tests

### Backend

```bash
cd consentflow-backend

# Full test suite
uv run pytest

# With coverage report
uv run pytest --cov=consentflow --cov-report=term-missing

# Specific test files
uv run pytest tests/test_consent.py          # Consent CRUD + revoke endpoints
uv run pytest tests/test_step3.py            # Gate 01: dataset gate (Presidio)
uv run pytest tests/test_step4.py            # Gate 03: inference enforcement (ASGI middleware)
uv run pytest tests/test_step5.py            # Gate 02: training gate (Kafka consumer)
uv run pytest tests/test_step7.py            # Gate 04: drift monitor
uv run pytest tests/test_monitoring_gate.py  # Monitoring gate unit tests
uv run pytest tests/test_policy_auditor.py   # Gate 05: LLM policy scanner
uv run pytest tests/test_gate05_e2e.py       # Gate 05: end-to-end policy scan
```

All tests must pass before opening a PR. New features should include corresponding tests.

### Extension

```bash
cd consentflow-extension
npm test     # runs vitest
```

---

## Submitting a Pull Request

1. **Check for an existing issue** — if none exists, open one using the appropriate template:
   - [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md)
   - [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md)

   Wait for a maintainer to assign it to you before starting work.

2. **Create your branch** from `main` on your fork (see [Branch Naming](#branch-naming)).

3. **Make your changes** — keep commits focused and atomic.

4. **Ensure all tests pass** (see [Running Tests](#running-tests)).

5. **Lint your code** (see [Code Style](#code-style)).

6. **Open a PR** against `main` and fill in the [PR template](.github/PULL_REQUEST_TEMPLATE.md) completely.

7. **Link the issue** — include `Closes #<issue-number>` in the PR description.

8. **One PR per issue** — don't bundle unrelated changes.

### PR Checklist

Before marking your PR as ready for review, confirm all of the following:

- [ ] My branch is up to date with `main`
- [ ] All existing tests pass (`uv run pytest` / `npm test`)
- [ ] I've added tests for new functionality
- [ ] I've run the linter with no new errors
- [ ] My commit messages follow Conventional Commits
- [ ] I've updated relevant docs (`README.md`, `backend.md`, `frontend.md`) if needed
- [ ] I've linked the issue this PR closes

---

## Issue Labels

| Label | Meaning |
|-------|---------|
| `good first issue` | Beginner-friendly, well-scoped |
| `bug` | Something is broken |
| `enhancement` | New feature or improvement |
| `documentation` | Docs-only change |
| `security` | Security-related concern |
| `backend` | Affects `consentflow-backend/` |
| `frontend` | Affects `consentflow-frontend/` |
| `extension` | Affects `consentflow-extension/` |
| `needs-triage` | Waiting for maintainer review |
| `wontfix` | Acknowledged but out of scope |

---

## Getting Help

- **GSSoC Discord / Slack** — tag `@Rishu7011` in the project channel
- **GitHub Discussions** — open a discussion for questions that aren't bugs
- **GitHub Issues** — use the issue templates for bugs and feature requests

If you're stuck on setup, open a `question` issue — no question is too small.

---

_Built with 🛡️ by contributors who believe consent revocation should mean something._