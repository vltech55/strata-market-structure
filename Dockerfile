# syntax=docker/dockerfile:1.7

# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 — builder: install build tools, resolve deps, produce a wheelhouse
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

# OS deps needed to compile uwsgi, cryptography, psycopg, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    libpcre3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Use uv for fast, reproducible installs; falls back to pip if uv unavailable.
RUN pip install --upgrade pip uv

WORKDIR /build
COPY pyproject.toml ./
# Compile a wheelhouse so the runtime stage doesn't need a toolchain.
RUN uv pip install --system --no-cache --target=/wheels -r <(uv pip compile pyproject.toml --extra dev 2>/dev/null || pip install --no-deps --target=/wheels '.[dev]')

# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime: slim image, only runtime libs + the prebuilt wheels
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    DJANGO_SETTINGS_MODULE=strata.settings

# Runtime-only OS deps (no compiler, no headers).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libpcre3 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root user so uwsgi / celery don't run as root.
RUN groupadd --system strata && useradd --system --gid strata --create-home strata
WORKDIR /app

COPY --from=builder /wheels /usr/local/lib/python3.13/site-packages
COPY --chown=strata:strata . /app

USER strata
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

# Default to uWSGI; compose overrides this for worker/beat/streamlit containers.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uwsgi", "--ini", "/app/observability/uwsgi.ini"]
