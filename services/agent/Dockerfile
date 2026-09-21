# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.source="https://github.com/yunoim/onchain-agent-platform" \
      org.opencontainers.image.description="On-chain question answering agent (FastAPI)" \
      org.opencontainers.image.licenses="MIT"

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    AGENT_HOST=0.0.0.0 \
    AGENT_PORT=8080

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).status == 200 else 1)"

ENTRYPOINT ["onchain-agent"]
