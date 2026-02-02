# CocoSearch All-in-One Docker Image
# Bundles PostgreSQL, Ollama (with pre-baked nomic-embed-text), and MCP server
# Uses s6-overlay for process supervision
#
# Build: docker build -t cocosearch -f docker/Dockerfile .
# Run:   docker run -v /path/to/code:/mnt/repos:ro -v cocosearch-data:/data -p 3000:3000 cocosearch

# =============================================================================
# Stage 1: Download Ollama model during build (not at runtime)
# Uses official Ollama image to download the model, then copies to final image
# =============================================================================
FROM ollama/ollama:latest AS model-downloader

# Start Ollama server in background, pull model, then stop
RUN ollama serve & \
    sleep 5 && \
    ollama pull nomic-embed-text && \
    pkill ollama

# =============================================================================
# Stage 2: Build the Python application with UV
# =============================================================================
FROM python:3.11-slim AS python-builder

# Install UV for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy project files for installation
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Create virtual environment and install the package
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python .

# =============================================================================
# Stage 3: Final runtime image
# =============================================================================
FROM python:3.11-slim

LABEL org.opencontainers.image.title="CocoSearch"
LABEL org.opencontainers.image.description="Local-first semantic code search with PostgreSQL, Ollama, and MCP"
LABEL org.opencontainers.image.source="https://github.com/VioletCranberry/coco-s"

# Build arguments
ARG S6_OVERLAY_VERSION=3.2.2.0
ARG TARGETARCH

# =============================================================================
# Install s6-overlay (PID 1 init system)
# Map Docker TARGETARCH to s6-overlay naming: arm64 -> aarch64, amd64 -> x86_64
# =============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends curl xz-utils ca-certificates && \
    S6_ARCH=$(case "${TARGETARCH}" in \
        "arm64") echo "aarch64" ;; \
        "amd64") echo "x86_64" ;; \
        *) echo "${TARGETARCH}" ;; \
    esac) && \
    curl -fsSL "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz" -o /tmp/s6-overlay-noarch.tar.xz && \
    curl -fsSL "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_ARCH}.tar.xz" -o /tmp/s6-overlay-${S6_ARCH}.tar.xz && \
    tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz && \
    tar -C / -Jxpf /tmp/s6-overlay-${S6_ARCH}.tar.xz && \
    rm /tmp/s6-overlay-*.tar.xz && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Install PostgreSQL 16 and runtime dependencies
# =============================================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gnupg2 \
        lsb-release \
        curl \
        ca-certificates \
        git && \
    # Add PostgreSQL APT repository
    echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-16 \
        postgresql-16-pgvector && \
    # Clean up
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# =============================================================================
# Install Ollama binary
# =============================================================================
# Copy Ollama binary from the model-downloader stage (already has correct arch)
COPY --from=model-downloader /bin/ollama /usr/local/bin/ollama

# =============================================================================
# Copy Python application from builder
# =============================================================================
COPY --from=python-builder /app/.venv /app/.venv
COPY --from=python-builder /build/src /app/src

# Add Python and PostgreSQL to PATH
ENV PATH="/app/.venv/bin:/usr/lib/postgresql/16/bin:$PATH"
ENV PYTHONPATH="/app/src"
# Set HOME for Ollama (required by envconfig)
ENV HOME="/root"

# =============================================================================
# Copy pre-baked Ollama model from downloader stage
# Note: Ollama stores models in ~/.ollama/models/, we need to copy just the
# models directory contents, not the parent .ollama directory
# =============================================================================
COPY --from=model-downloader /root/.ollama/models /data/ollama_models

# =============================================================================
# Create directory structure
# =============================================================================
RUN mkdir -p /data/pg_data /data/ollama_models /data/cocosearch /mnt/repos

# =============================================================================
# Environment variables (from CONTEXT.md decisions)
# =============================================================================
ENV COCOSEARCH_MCP_PORT=3000 \
    COCOSEARCH_PG_PORT=5432 \
    COCOSEARCH_OLLAMA_PORT=11434 \
    COCOSEARCH_EMBED_MODEL=nomic-embed-text \
    COCOSEARCH_MCP_TRANSPORT=http \
    COCOSEARCH_LOG_LEVEL=warn \
    # Ollama configuration
    OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_MODELS=/data/ollama_models \
    # PostgreSQL configuration
    PGDATA=/data/pg_data \
    # CocoSearch database URL
    COCOSEARCH_DATABASE_URL=postgresql://cocosearch:cocosearch@localhost:5432/cocosearch \
    # s6-overlay graceful shutdown timing (10 seconds)
    S6_KILL_GRACETIME=10000 \
    S6_SERVICES_GRACETIME=10000

# =============================================================================
# Copy s6 service definitions (rootfs overlay)
# =============================================================================
COPY docker/rootfs/ /

# =============================================================================
# Expose ports
# =============================================================================
EXPOSE 3000 5432 11434

# =============================================================================
# Health check - all services must be ready
# --start-period: Ignore failures during first 90s (startup grace period)
# --interval: Check every 30s after start period
# --timeout: Allow 10s for each check
# --retries: Mark unhealthy after 3 consecutive failures
# =============================================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD /etc/s6-overlay/scripts/health-check || exit 1

# =============================================================================
# Signal handling for graceful shutdown
# Use SIGTERM for s6-overlay, which will cascade to services
# PostgreSQL finish script handles fast shutdown
# =============================================================================
STOPSIGNAL SIGTERM

# =============================================================================
# Use s6-overlay as init
# =============================================================================
ENTRYPOINT ["/init"]
