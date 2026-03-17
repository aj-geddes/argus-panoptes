# Argus Panoptes

**The all-seeing eye for your AI agents.**

Argus Panoptes is a self-hosted, unified observability platform for AI agent frameworks. It tracks performance, costs, and behavior across LangGraph, CrewAI, OpenAI Agents SDK, Google ADK, AutoGen, PydanticAI, and any framework that emits OpenTelemetry GenAI spans.

Named after the hundred-eyed giant of Greek mythology, Argus watches every agent, every trace, every token, every dollar -- nothing escapes its gaze.

## Features

- **Framework-agnostic ingestion** -- accepts OpenTelemetry GenAI Semantic Conventions v1.37 spans via REST API
- **Cost tracking** -- automatic per-token cost calculation for OpenAI, Anthropic, Google, DeepSeek, xAI, Mistral, and Meta models
- **Real-time dashboard** -- live-updating metrics via Server-Sent Events (SSE), built with HTMX + Alpine.js
- **Trace visualization** -- searchable trace explorer with span tree rendering
- **Configurable alerting** -- rule-based alerts with webhook notifications (Slack, etc.)
- **Hot-reload configuration** -- edit `config/argus.yaml` and changes apply live, zero downtime
- **Dual database support** -- SQLite for development, PostgreSQL for production, same codebase
- **API key authentication** -- optional API key auth for ingestion endpoints
- **Rate limiting** -- configurable per-client rate limiting on ingestion
- **Lightweight frontend** -- HTMX + Alpine.js + Tailwind CSS, zero JS build step, under 31KB total JS

## Quick Start

### Docker (recommended)

```bash
# Clone the repository
git clone https://github.com/aj-geddes/argus-panoptes.git
cd argus-panoptes

# Start with Docker Compose (development mode with hot-reload)
cd docker
docker compose up

# Open the dashboard
open http://localhost:8000
```

### Docker (production)

```bash
# Build the production image
docker build -t argus-panoptes -f docker/Dockerfile .

# Run with default SQLite
docker run -p 8000:8000 argus-panoptes

# Run with PostgreSQL
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@db-host:5432/argus" \
  -e ARGUS_API_KEY="your-secret-key" \
  argus-panoptes
```

### Local Development

```bash
# Prerequisites: Python 3.12+
python -m venv .venv
source .venv/bin/activate

# Install with development dependencies
pip install -e ".[dev]"

# Run the development server
uvicorn argus.main:app --reload --reload-dir src

# Open the dashboard
open http://localhost:8000
```

## Configuration

All configuration lives in `config/argus.yaml` and is **hot-reloaded** -- edit the file and changes apply instantly without restarting the server.

Copy the example config to get started:

```bash
cp config/argus.example.yaml config/argus.yaml
```

### Database

```yaml
database:
  # SQLite for development (default):
  url: "sqlite+aiosqlite:///./argus.db"

  # PostgreSQL for production:
  # url: "postgresql+asyncpg://user:pass@localhost:5432/argus"

  pool_size: 10
```

You can also set the database URL via the `DATABASE_URL` environment variable.

### Security

```yaml
security:
  api_key_auth:
    enabled: true
    header_name: "X-API-Key"
    key: "your-secret-api-key"  # Or set ARGUS_API_KEY env var
  rate_limiting:
    enabled: true
    requests_per_window: 1000
    window_seconds: 60
```

### Cost Model

Token pricing is configured per-provider, per-model (per million tokens):

```yaml
cost_model:
  providers:
    openai:
      gpt-5.4: { input: 2.50, output: 10.00 }
    anthropic:
      claude-opus-4-6: { input: 5.00, output: 25.00 }
```

### Alerts

```yaml
alerts:
  enabled: true
  rules:
    - name: "High error rate"
      condition: "error_rate > 0.10"
      window: "5m"
      severity: "critical"
      notify: ["webhook"]
```

## API

### Ingestion

Send OpenTelemetry GenAI spans to the ingestion endpoint:

```bash
curl -X POST http://localhost:8000/v1/traces \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "resourceSpans": [{
      "resource": {
        "attributes": [
          {"key": "gen_ai.agent.name", "value": {"stringValue": "my-agent"}}
        ]
      },
      "scopeSpans": [{
        "spans": [{
          "traceId": "abc123",
          "spanId": "span456",
          "name": "chat gpt-4o",
          "startTimeUnixNano": "1710000000000000000",
          "endTimeUnixNano": "1710000001000000000",
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

### REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/v1/traces` | Ingest OTLP trace data |
| `GET` | `/api/v1/agents` | List registered agents |
| `GET` | `/api/v1/agents/{id}` | Get agent details |
| `GET` | `/api/v1/agents/{id}/metrics` | Get agent metrics |
| `GET` | `/api/v1/traces` | Search traces |
| `GET` | `/api/v1/traces/{id}` | Get trace details |
| `GET` | `/api/v1/metrics/summary` | Get metrics summary |
| `GET` | `/api/v1/alerts` | List alert rules |
| `GET` | `/api/v1/config` | Get current config |
| `PUT` | `/api/v1/config` | Update config |

### Framework Integration

| Framework | Integration Method |
|-----------|-------------------|
| LangGraph / LangChain | OTel collector -- set `OTEL_EXPORTER_OTLP_ENDPOINT` |
| CrewAI | Native OTel instrumentation |
| OpenAI Agents SDK | OTel Python SDK wrapper or Argus SDK shim |
| Google ADK | OTel collector |
| PydanticAI | Native OTel support |
| AutoGen | `opentelemetry-instrumentation-autogen` |
| Semantic Kernel | Microsoft OTel integration |
| Custom agents | REST API or Argus Python SDK |

### Python SDK

For frameworks without native OTel support, use the Argus SDK:

```python
from argus.sdk.reporter import ArgusReporter

reporter = ArgusReporter(
    endpoint="http://localhost:8000",
    agent_name="my-agent",
    api_key="your-api-key",  # optional
)

await reporter.report_span(
    operation="chat",
    model="gpt-4o",
    input_tokens=150,
    output_tokens=50,
    latency_ms=1200,
)
```

## Architecture

```
Agent Frameworks (LangGraph, CrewAI, OpenAI, ...)
         |
         | OTLP/REST
         v
  Ingestion Layer (/v1/traces)
         |
         v
  Argus Core (FastAPI)
  +-- Metrics Engine (windowed aggregation)
  +-- Cost Calculator (config-driven pricing)
  +-- Alert Engine (rule evaluation + webhooks)
  +-- Config Manager (hot-reload via watchdog)
  +-- SSE Broadcaster (real-time updates)
         |
         | HTML partials via SSE
         v
  Frontend (HTMX + Alpine.js + Tailwind)
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, SQLModel, SQLAlchemy async |
| Frontend | HTMX 2.x, Alpine.js 3.x, Tailwind CSS 4.x |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Real-time | Server-Sent Events (SSE) |
| Config | YAML with watchdog hot-reload |
| Container | Docker multi-stage, non-root |

## Database Migrations

Argus uses Alembic for database schema migrations, supporting both SQLite and PostgreSQL:

```bash
# Run migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "description"

# Use PostgreSQL
DATABASE_URL="postgresql+asyncpg://user:pass@localhost/argus" alembic upgrade head
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src/argus --cov-report=term-missing

# Run a specific test file
pytest tests/unit/test_security.py -v

# Lint and type check
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/argus/
```

## Project Structure

```
argus-panoptes/
+-- config/              # YAML configuration (hot-reloaded)
+-- src/argus/
|   +-- core/            # Config, database, SSE, security
|   +-- models/          # SQLModel data models
|   +-- routes/api/      # REST API endpoints
|   +-- routes/views/    # HTMX view routes
|   +-- services/        # Business logic
|   +-- schemas/         # Pydantic request/response schemas
|   +-- sdk/             # Python SDK for non-OTel frameworks
+-- tests/               # pytest test suite
+-- migrations/          # Alembic database migrations
+-- docker/              # Dockerfiles and compose
+-- static/              # CSS, JS assets
+-- .github/workflows/   # CI/CD pipelines
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, testing, and PR process.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting guidelines.

## License

Apache License 2.0. See [LICENSE](LICENSE) for the full text.
