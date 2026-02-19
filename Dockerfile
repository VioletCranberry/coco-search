# Stage 1: Builder
FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

COPY src/ src/
COPY README.md .
RUN uv sync --no-dev --frozen

# Stage 2: Runtime
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv .venv
COPY --from=builder /app/src src
COPY pyproject.toml .

ENV PATH="/app/.venv/bin:$PATH"
ENV COCOSEARCH_NO_DASHBOARD=1
ENV COCOSEARCH_MCP_PORT=3000

EXPOSE ${COCOSEARCH_MCP_PORT}

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:${COCOSEARCH_MCP_PORT}/health

ENTRYPOINT ["cocosearch"]
CMD ["mcp", "--transport", "sse"]
