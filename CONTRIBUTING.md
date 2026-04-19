# 🚀 New Contributor Guide

Welcome to **ConsentFlow**! 🎉 We are thrilled to have you here, especially if you are participating in **GSSoC '26**. This guide will walk you through everything you need to get started — from your very first issue claim to opening a polished Pull Request.

---

## 📋 Table of Contents

1. [Prerequisites](#-1-prerequisites)
2. [Understanding the Project](#-2-understanding-the-project)
3. [Claiming an Issue](#-3-claiming-an-issue)
4. [Assignment Rules (Important!)](#-4-assignment-rules-important)
5. [Local Setup](#-5-local-setup)
6. [Branching Strategy](#-6-branching-strategy)
7. [Commit Message Format](#-7-commit-message-format)
8. [Opening a Pull Request](#-8-opening-a-pull-request)
9. [GSSoC Scoring](#-9-gssoc-scoring)
10. [Getting Help](#-10-getting-help)

---

## 🛠️ 1. Prerequisites

Before you begin, ensure you have the following installed on your machine:

| Tool | Version | Purpose |
|------|---------|---------|
| Docker + Docker Compose | v2+ | Runs Kafka, Redis, Postgres, Zookeeper |
| Node.js | 20+ | Frontend Dashboard & Chrome Extension |
| Python | 3.12+ | FastAPI Backend |
| `uv` | latest | Python package manager (replaces pip) |
| Git | any | Version control |

---

## 🏗️ 2. Understanding the Project

ConsentFlow has **three main components**. Before picking an issue, understand which component it belongs to:

| Component | Location | Tech Stack |
|-----------|----------|-----------|
| **Backend** | `consentflow-backend/` | Python 3.12, FastAPI, Kafka, Redis, PostgreSQL |
| **Frontend** | `consentflow-frontend/` | Next.js 16 (App Router), TypeScript |
| **Extension** | `consentflow-extension/` | Manifest V3, Vanilla JS, Vitest |

---

## 🌱 3. Claiming an Issue

1. Browse the [Issues tab](../../issues) and look for `good first issue` or `help wanted` labels.
2. Read the issue **fully** before claiming — check if it is already assigned.
3. Comment one of the following on the issue to claim it:
   - `.take`
   - `/assign`
   - `assign me`
4. Our **Auto-Assign Bot** will automatically assign the issue to you within seconds!

> [!NOTE]
> Do NOT open a PR without a linked issue. Every PR must reference an issue number.

---

## ⚠️ 4. Assignment Rules (Important!)

To ensure fairness during GSSoC and give everyone a chance to contribute:

- **You can hold a maximum of 3 open issues at a time.**
- If you already have 3 open issues assigned, our **Assignment Limit Enforcer Bot** will automatically unassign you from any new issue you try to claim and notify you.
- Once you close/merge one of your open issues, you are free to claim another.
- Maintainers and admins are exempt from this rule.

---

## 💻 5. Local Setup

### Step 1: Fork & Clone

```bash
# Fork the repo on GitHub, then clone your fork:
git clone https://github.com/<your-username>/ConsentFlow.git
cd ConsentFlow
```

### Step 2: Set up the Backend

```bash
cd consentflow-backend

# Copy the environment file
cp .env.example .env       # Linux / Mac
copy .env.example .env     # Windows

# Edit .env — at minimum set GEMINI_API_KEY or MISTRAL_API_KEY
# Then start the full Docker stack:
docker compose up --build
```

This starts PostgreSQL 16, Redis 7, Zookeeper, Kafka, and the ConsentFlow API.
All 6 database migrations are applied automatically at startup.

### Step 3: Set up the Frontend

```bash
cd consentflow-frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Step 4: Set up the Chrome Extension

```bash
cd consentflow-extension
npm install
npm run build
```

Then in Chrome:
1. Go to `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked** → select the `consentflow-extension/dist` folder

### Step 5: Run Tests

```bash
# Backend tests
cd consentflow-backend
uv run pytest --tb=short -q

# Extension tests
cd consentflow-extension
npm test
```

---

## 🌿 6. Branching Strategy

Always create a new branch from `main` for your work. **Never commit directly to `main`.**

```bash
git checkout main
git pull origin main
git checkout -b type/short-description
```

**Branch naming format:** `type/short-description`

| Type | Example |
|------|---------|
| `feat` | `feat/add-redis-cache` |
| `bug` | `bug/fix-inference-gate` |
| `docs` | `docs/update-contributing` |
| `refactor` | `refactor/clean-kafka-consumer` |
| `ci` | `ci/add-codeql-scan` |

---

## ✍️ 7. Commit Message Format

All commit messages must follow the **Conventional Commits** format:

```
type(scope): short description
```

**Examples:**

```bash
feat(backend): add Redis bloom filter for Gate 03
bug(extension): fix PII token reversal for Aadhaar
docs(readme): update quick start instructions
ci(workflows): add CodeQL security scan
refactor(frontend): simplify pipeline gate animation
```

**Valid types:** `feat`, `bug`, `docs`, `refactor`, `test`, `ci`, `perf`, `chore`  
**Valid scopes:** `backend`, `frontend`, `extension`, `ci`, `docker`, `readme`

---

## 🚀 8. Opening a Pull Request

1. Push your branch to your fork:
   ```bash
   git push origin type/short-description
   ```
2. Go to GitHub → Open a **Pull Request** against the `main` branch of `ConsentFlow`.
3. Fill in the **Pull Request Template** completely — do not delete any sections.
4. Link your issue using `Closes #<issue-number>` in the PR description.
5. Add appropriate **difficulty labels** (`level:beginner`, `level:intermediate`, `level:advanced`) — this is required for GSSoC scoring.

Once your PR is opened, our bots will automatically:
- ✅ Run the CI pipeline for your specific component
- ✅ Run a CodeQL security scan
- ✅ Apply labels based on your PR title and changed files
- ✅ Calculate your GSSoC score
- ✅ Flag your PR if it is too small or missing labels

---

## 🏆 9. GSSoC Scoring

PRs are automatically scored by our **GSSoC Score Calculator Bot**:

| Label | Points |
|-------|--------|
| `gssoc:approved` | 50 base points |
| `level:beginner` | +10 points |
| `level:intermediate` | +25 points |
| `level:advanced` | +55 points |
| `level:critical` | +100 points |
| `quality:clean` | 1.2x multiplier |
| `quality:exceptional` | 1.5x multiplier |

> [!IMPORTANT]
> You **must** have both `gssoc:approved` AND a `level:*` label on your PR for it to be counted on the leaderboard. Missing labels will trigger an automated warning comment.

---

## 🙋 10. Getting Help

- **Stuck on setup?** Open a [Discussion](../../discussions) or comment on your issue.
- **Found a bug in the codebase?** Open a [Bug Report](../../issues/new?template=bug_report.md).
- **Have a feature idea?** Open a [Feature Request](../../issues/new?template=feature_request.md).

---

<div align="center">

**When a user says stop — everything stops.**  
*Build responsibly. Welcome to the team!* 🛡️

</div>