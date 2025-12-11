# syntax=docker/dockerfile:1

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install uv using the official installer (more reliable than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-dev

COPY . .

RUN uv sync --frozen --no-dev

RUN groupadd --system app \
    && useradd --system --gid app --home /app app \
    && chown -R app:app /app

ENV PATH="/app/.venv/bin:${PATH}"

USER app

EXPOSE 8000

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
