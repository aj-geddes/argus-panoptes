# Multi-stage production Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runtime

RUN groupadd -r argus && useradd -r -g argus -d /app argus
WORKDIR /app

COPY --from=builder /install /usr/local
COPY src/ src/
COPY static/ static/
COPY config/argus.example.yaml config/argus.yaml
COPY migrations/ migrations/
COPY alembic.ini .

RUN chown -R argus:argus /app
USER argus

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

EXPOSE 8000
CMD ["uvicorn", "argus.main:app", "--host", "0.0.0.0", "--port", "8000"]
