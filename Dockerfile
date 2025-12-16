# syntax=docker/dockerfile:1

FROM python:3.13-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=hardlink

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libgfortran5 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-install-project   # <-- keep dev deps if uvicorn is dev-only

COPY . .

FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libgfortran5 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app

USER nobody

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
