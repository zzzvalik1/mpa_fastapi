# syntax=docker/dockerfile:1.7

# ---------- Builder stage ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build deps for cryptography / bcrypt.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        libffi-dev \
        pkg-config \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ---------- Runtime stage ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    APP_HOME=/app

# Minimal runtime deps (libssl for cryptography/bcrypt, no compilers).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libssl3 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtualenv from the builder stage.
COPY --from=builder /opt/venv /opt/venv

WORKDIR ${APP_HOME}

# Copy application source.
COPY app/ ./app/
COPY pyproject.toml README.md .env.example ./

# Pre-create the log directory so the rotating handler can write immediately.
RUN mkdir -p storage/logs

# Non-root user for runtime.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser ${APP_HOME}
USER appuser

EXPOSE 8080

# Uvicorn entry point (sync workers; push endpoints are not async).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
