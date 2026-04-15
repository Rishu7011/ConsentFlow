# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install system dependencies for asyncpg (requires gcc + libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast pip-compatible installer/manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock README.md ./

# Increase UV network timeout to prevent timeouts on large packages
ENV UV_HTTP_TIMEOUT=300

# Install production dependencies only, skipping the project source installation (caching layer)
RUN uv sync --no-dev --no-install-project

# Copy application source
COPY consentflow/ ./consentflow/

# Install the project itself
RUN uv sync --no-dev

# Download spaCy NLP model required by Presidio (anonymizer.py)
# en_core_web_lg gives best NER accuracy for PII detection
# We use uv pip install directly instead of spacy download to prevent pip from hanging silently
RUN uv pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl"

# Expose the port uvicorn listens on
EXPOSE 8000

# Run the ASGI server via uv so the virtualenv is automatically activated
CMD ["uv", "run", "uvicorn", "consentflow.app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
