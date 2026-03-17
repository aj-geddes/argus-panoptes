---
title: "Getting Started"
description: "Install Argus Panoptes and send your first trace in under two minutes."
layout: page
---

## Prerequisites

- **Docker** (recommended) — Docker Engine 20.10+ and Docker Compose v2
- **OR** Python 3.12+ for local setup

---

## Docker Quickstart (recommended)

The fastest way to run Argus Panoptes is with Docker Compose. This starts the app
with hot-reload and a Tailwind CSS watcher.

```bash
# Clone the repository
git clone https://github.com/aj-geddes/argus-panoptes.git
cd argus-panoptes

# Start with Docker Compose
cd docker
docker compose up
```

The dashboard is now available at **[http://localhost:8000](http://localhost:8000)**.

That's it. No config required for local development — Argus uses SQLite by default.

---

## Docker Production

```bash
# Build the production image
docker build -t argus-panoptes -f docker/Dockerfile .

# Run with SQLite (simplest)
docker run -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  argus-panoptes

# Run with PostgreSQL + API key
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@db-host:5432/argus" \
  -e ARGUS_API_KEY="your-secret-key" \
  -v $(pwd)/config:/app/config \
  argus-panoptes
```

---

## Local Development Setup

```bash
# Prerequisites: Python 3.12+
git clone https://github.com/aj-geddes/argus-panoptes.git
cd argus-panoptes

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# Install with development dependencies
pip install -e ".[dev]"

# Copy the example config
cp config/argus.example.yaml config/argus.yaml

# Run database migrations
alembic upgrade head

# Start the development server with hot-reload
uvicorn argus.main:app --reload --reload-dir src
```

Open [http://localhost:8000](http://localhost:8000).

---

## First Login

Argus Panoptes has no login screen by default — the dashboard is open. To enable
API key authentication for ingestion endpoints, edit `config/argus.yaml`:

```yaml
security:
  api_key_auth:
    enabled: true
    header_name: "X-API-Key"
    key: "your-secret-api-key"
```

Or set the environment variable:

```bash
ARGUS_API_KEY="your-secret-api-key"
```

---

## Send Your First Trace

Once Argus is running, send a test span to verify ingestion:

```bash
curl -X POST http://localhost:8000/v1/traces \
  -H "Content-Type: application/json" \
  -d '{
    "resourceSpans": [{
      "resource": {
        "attributes": [
          {"key": "gen_ai.agent.name", "value": {"stringValue": "hello-agent"}}
        ]
      },
      "scopeSpans": [{
        "spans": [{
          "traceId": "aabbccddeeff00112233445566778899",
          "spanId": "aabbccddeeff0011",
          "name": "chat gpt-4o",
          "startTimeUnixNano": "1710000000000000000",
          "endTimeUnixNano": "1710000001200000000",
          "attributes": [
            {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
            {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
            {"key": "gen_ai.provider.name", "value": {"stringValue": "openai"}},
            {"key": "gen_ai.usage.input_tokens", "value": {"intValue": 150}},
            {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 50}}
          ]
        }]
      }]
    }]
  }'
```

Expected response:

```json
{"accepted": 1, "rejected": 0}
```

Refresh the dashboard — you should see **hello-agent** appear in the agent list.

---

## Health Check

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "database": "ok",
  "config": "loaded",
  "version": "0.1.0"
}
```

---

## Troubleshooting

**Port 8000 is already in use**

```bash
# Find what's using port 8000
lsof -ti:8000

# Or run Argus on a different port
uvicorn argus.main:app --port 8080
```

**Database errors on startup**

Run migrations manually:

```bash
alembic upgrade head
```

**Config file not found**

```bash
cp config/argus.example.yaml config/argus.yaml
```

**Docker Compose "network not found" error**

```bash
docker compose down --volumes
docker compose up --build
```

**Spans not appearing in the dashboard**

1. Check the ingestion endpoint responds with `{"accepted": N}` (N > 0)
2. Verify `gen_ai.agent.name` is set in the resource attributes
3. Check the server logs: `docker compose logs app`

---

## Next Steps

- [API Reference]({{ '/api-reference' | relative_url }}) — full endpoint documentation
- [Configuration]({{ '/configuration' | relative_url }}) — customize every setting
- [Python SDK]({{ '/sdk' | relative_url }}) — integrate with custom agents
- [Deployment]({{ '/deployment' | relative_url }}) — production setup with PostgreSQL
