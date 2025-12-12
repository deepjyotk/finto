# syntax=docker/dockerfile:1

# ====================================================================
# 1. BUILDER STAGE: Compile and Install Dependencies
# ====================================================================
FROM python:3.13-slim-bookworm AS builder

# Environment variables for build process
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # FIX: Change to hardlink mode. This is the direct fix for the NumPy "ELF load command" error.
    UV_LINK_MODE=hardlink \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_HTTP_TIMEOUT=60

WORKDIR /app

# Install build dependencies: build-essential for compiling C-extensions, libpq-dev for psycopg/asyncpg
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    # Install libgfortran5, which is often a runtime dependency for OpenBLAS (NumPy/SciPy)
        libgfortran5 \
    && rm -rf /var/lib/apt/lists/*

# Install uv from its official source
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Install dependencies into /app/.venv
# We keep the lock file separate to leverage Docker caching when only code changes
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Cleanup the virtual environment *before* copying to the next stage
# NOTE: Removed the 'strip' command which is a known cause of the 'ELF load command' error.
RUN find /app/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /app/.venv -type f -name "*.pyc" -delete \
    && find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
    && find /app/.venv -type d -name "*.dist-info" -exec sh -c 'rm -rf "$1"/RECORD "$1"/INSTALLER "$1"/direct_url.json 2>/dev/null || true' _ {} \; \
    && rm -rf /app/.venv/lib/python*/site-packages/pip* 2>/dev/null || true


# ====================================================================
# 2. RUNTIME STAGE: Minimal image for production
# ====================================================================
# Using a minimal Debian image (not the Python image) for the smallest size
FROM debian:bookworm-slim AS runtime

# Environment variables for the runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install only the absolute runtime dependencies
# libpq5 for PostgreSQL client, python3 and python3-venv to run the venv
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy the built virtual environment and Python binaries from the builder stage
# This is the VIRTUAL_ENV itself
COPY --from=builder /app/.venv /app/.venv

# Set PATH to use the venv binaries
ENV PATH="/app/.venv/bin:${PATH}"

# Copy application code *after* dependencies to maximize caching
COPY . .

# Create non-root user and set permissions
RUN groupadd --system app \
    && useradd --system --gid app --home /app app \
    && chown -R app:app /app

USER app

EXPOSE 8000

# Use exec format for CMD for better process signal handling
CMD ["/app/.venv/bin/uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]