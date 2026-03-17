# =============================================================================
# Argus Panoptes — Production Docker Image
# Multi-stage build, non-root user, health checks
# =============================================================================

# Stage 1: Builder — install Python dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies (gcc needed for some native extensions)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy only dependency specification first for better layer caching
COPY pyproject.toml .

# Install dependencies into a dedicated prefix
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime — minimal production image
FROM python:3.12-slim AS runtime

# Build arguments for image labels
ARG BUILD_DATE
ARG VCS_REF

LABEL org.opencontainers.image.title="Argus Panoptes" \
      org.opencontainers.image.description="The all-seeing eye for your AI agents" \
      org.opencontainers.image.source="https://github.com/aj-geddes/argus-panoptes" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="Apache-2.0"

# Create non-root user and group
RUN groupadd -r argus && useradd -r -g argus -d /app -s /sbin/nologin argus

WORKDIR /app

# Copy installed dependencies from builder stage
COPY --from=builder /install /usr/local

# Copy application source and assets
COPY src/ src/
COPY static/ static/
COPY config/argus.example.yaml config/argus.yaml
COPY migrations/ migrations/
COPY alembic.ini .

# Create data directory for SQLite and set ownership
RUN mkdir -p /app/data && chown -R argus:argus /app

# Switch to non-root user
USER argus

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ARGUS_CONFIG_PATH=/app/config/argus.yaml

# Health check: verify the app responds to /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

EXPOSE 8000

CMD ["uvicorn", "argus.main:app", "--host", "0.0.0.0", "--port", "8000"]
