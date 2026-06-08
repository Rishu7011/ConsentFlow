# Contributing to ConsentFlow

Thank you for considering contributing to ConsentFlow! We welcome contributions of all kinds — bug fixes, new features, documentation improvements, and more.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

## Code of Conduct

This project adheres to the [Contributor Covenant](https://www.contributor-covenant.org/). By participating, you are expected to uphold this code. Please report unacceptable behavior to the maintainers.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/ConsentFlow.git
   cd ConsentFlow
   ```
3. Set up the development environment (see [Development Setup](#development-setup))
4. Create a branch for your work:
   ```bash
   git checkout -b feat/your-feature-name
   ```

## Development Setup

### Backend (FastAPI)

```bash
cd consentflow-backend
cp .env.example .env
# Edit .env with your API keys (GEMINI_API_KEY or MISTRAL_API_KEY)
docker compose up --build
```

### Frontend (Next.js)

```bash
cd consentflow-frontend
npm install
npm run dev
```

### Chrome Extension

```bash
cd consentflow-extension
npm install
npm run build
```

See the main [README](README.md) for detailed instructions.

## Project Structure

```
ConsentFlow/
├── consentflow-backend/     # FastAPI backend with enforcement gates
│   ├── consentflow/         # Core library (gates, SDK, telemetry)
│   │   └── app/             # FastAPI application
│   ├── tests/               # Test suite
│   └── migrations/          # Database migrations
├── consentflow-frontend/    # Next.js 16 dashboard
│   ├── app/                 # App Router pages & API routes
│   └── components/          # React components
└── consentflow-extension/   # Chrome MV3 extension
    └── src/                 # Extension source code
```

## Coding Standards

### Python

- Target Python 3.12+
- Format with [Ruff](https://docs.astral.sh/ruff/):
  ```bash
  cd consentflow-backend
  ruff check .
  ruff format .
  ```
- Type hints are required on all public functions
- Line length: 100 characters

### TypeScript / React

- Use TypeScript strict mode
- Follow the existing component patterns in `components/`
- Use the App Router conventions for pages
- Run linting:
  ```bash
  cd consentflow-frontend
  npm run lint
  ```

### Commit Messages

Use conventional commits:

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation
- `refactor:` — code restructuring
- `test:` — adding/updating tests
- `chore:` — maintenance tasks

## Testing

### Backend Tests

```bash
cd consentflow-backend
uv run pytest                    # Full suite
uv run pytest --cov=consentflow  # With coverage
uv run pytest tests/test_step4.py  # Specific test
```

### Extension Tests

```bash
cd consentflow-extension
npm test
```

Please ensure all tests pass before submitting a PR. Add tests for new functionality.

## Pull Request Process

1. Ensure your branch is up to date with `main`
2. Run the full test suite and linting
3. Update documentation if your changes affect the API or user-facing behavior
4. Fill out the [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md)
5. Request review from the maintainers
6. Address any review feedback

## Issue Reporting

- Use the [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md) for bugs
- Use the [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md) for feature ideas
- Search existing issues before opening a new one
- Provide clear reproduction steps for bugs

## Questions?

Open a [Discussion](https://github.com/Siddh2024/ConsentFlow/discussions) or reach out to the maintainers.

---

We appreciate every contribution — thank you for helping make ConsentFlow better!
