---
title: "Configuration"
description: "Every configuration option in config/argus.yaml with examples, environment variables, and hot-reload behavior."
layout: page
---

All Argus Panoptes configuration lives in `config/argus.yaml`. The file is
**hot-reloaded** — edit it while the server is running and changes apply
immediately with zero downtime. Invalid YAML is rejected and the old config
stays active.

```bash
cp config/argus.example.yaml config/argus.yaml
```

---

## server

Controls the FastAPI/Uvicorn server.

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  log_level: "INFO"
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `host` | string | `"0.0.0.0"` | Bind address |
| `port` | int | `8000` | HTTP port |
| `workers` | int | `4` | Uvicorn worker processes |
| `log_level` | string | `"INFO"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## database

Configures the database backend.

```yaml
database:
  url: "sqlite+aiosqlite:///./argus.db"
  # url: "postgresql+asyncpg://user:pass@localhost/argus"
  pool_size: 10
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `url` | string | SQLite | SQLAlchemy async database URL |
| `pool_size` | int | `10` | Connection pool size (PostgreSQL) |

**Environment variable override:**

```bash
DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/argus"
```

The `DATABASE_URL` environment variable takes precedence over the config file.

---

## ingestion

Controls the span ingestion endpoints.

```yaml
ingestion:
  otlp_enabled: true
  otlp_port: 4318
  rest_enabled: true
  max_batch_size: 1000
  flush_interval_seconds: 5
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `otlp_enabled` | bool | `true` | Enable OTLP/HTTP collector on `otlp_port` |
| `otlp_port` | int | `4318` | OTLP/HTTP listen port |
| `rest_enabled` | bool | `true` | Enable `POST /v1/traces` REST endpoint |
| `max_batch_size` | int | `1000` | Maximum spans per ingestion request |
| `flush_interval_seconds` | int | `5` | SDK batch flush interval |

---

## metrics

Controls metrics aggregation and retention.

```yaml
metrics:
  aggregation_windows: ["1m", "5m", "1h", "1d"]
  retention_days: 90
  snapshot_interval_seconds: 60
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `aggregation_windows` | list | `["1m","5m","1h","1d"]` | Time windows for pre-aggregated snapshots |
| `retention_days` | int | `90` | How long to keep raw trace data |
| `snapshot_interval_seconds` | int | `60` | How often to compute metric snapshots |

---

## cost_model

Per-provider, per-model token pricing (USD per million tokens).

```yaml
cost_model:
  providers:
    openai:
      gpt-4o:      { input: 2.50, output: 10.00 }
      gpt-4o-mini: { input: 0.15, output: 0.60 }
    anthropic:
      claude-sonnet-4-6: { input: 3.00, output: 15.00 }
    google:
      gemini-2.5-pro: { input: 1.25, output: 10.00 }
    deepseek:
      deepseek-v3.2: { input: 0.28, output: 0.42 }
    xai:
      grok-3: { input: 3.00, output: 15.00 }
    mistral:
      mistral-large: { input: 2.00, output: 6.00 }
    meta:
      llama-4-maverick: { input: 0.20, output: 0.60 }
```

All prices are **USD per million tokens**. Add any model by adding a key.
The provider name is matched against the `gen_ai.provider.name` span attribute.
The model name is matched against `gen_ai.request.model`.

If a model is not found in the pricing table, cost is reported as `null`.

---

## security

Controls API key authentication and rate limiting.

```yaml
security:
  api_key_auth:
    enabled: false
    header_name: "X-API-Key"
    # key: "your-secret-api-key"  # Or set ARGUS_API_KEY env var

  rate_limiting:
    enabled: false
    requests_per_window: 1000
    window_seconds: 60
```

### api_key_auth

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | `false` | Require API key on all ingestion endpoints |
| `header_name` | string | `"X-API-Key"` | Request header to read the key from |
| `key` | string | — | The expected API key value |

**Environment variable:**

```bash
ARGUS_API_KEY="your-secret-api-key"
```

Keys are compared in constant time to prevent timing attacks.

### rate_limiting

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | `false` | Enable per-client rate limiting |
| `requests_per_window` | int | `1000` | Max requests per time window |
| `window_seconds` | int | `60` | Rate limit window duration |

---

## alerts

Rule-based alerting with configurable conditions.

```yaml
alerts:
  enabled: true
  check_interval_seconds: 30
  rules:
    - name: "High error rate"
      condition: "error_rate > 0.10"
      window: "5m"
      severity: "critical"
      notify: ["webhook"]

    - name: "Cost spike"
      condition: "cost_usd_per_hour > 50.00"
      window: "1h"
      severity: "warning"
      notify: ["webhook"]
```

| Setting | Type | Description |
|---------|------|-------------|
| `enabled` | bool | Enable the alert engine |
| `check_interval_seconds` | int | How often to evaluate rules |
| `rules[].name` | string | Human-readable rule name |
| `rules[].condition` | string | Alert expression (see below) |
| `rules[].window` | string | Aggregation window: `1m`, `5m`, `1h`, `1d` |
| `rules[].severity` | string | `critical`, `warning`, `info` |
| `rules[].notify` | list | Notification channels: `["webhook"]` |

### Alert Conditions

| Variable | Description |
|----------|-------------|
| `error_rate` | Fraction of spans with errors (0.0 – 1.0) |
| `cost_usd_per_hour` | Projected hourly cost in USD |
| `p95_latency_ms` | 95th percentile latency in milliseconds |
| `p99_latency_ms` | 99th percentile latency in milliseconds |
| `total_spans` | Total span count in the window |

Supported operators: `>`, `<`, `>=`, `<=`, `==`, `!=`.

---

## webhooks

HTTP webhook destinations for alert notifications.

```yaml
webhooks:
  - name: "slack-alerts"
    url: "${SLACK_WEBHOOK_URL}"
    events: ["alert.fired", "alert.resolved"]
```

| Setting | Type | Description |
|---------|------|-------------|
| `name` | string | Identifier for logs |
| `url` | string | HTTP endpoint (supports `${ENV_VAR}` substitution) |
| `events` | list | Which events to send: `alert.fired`, `alert.resolved` |

**Webhook payload:**

```json
{
  "event": "alert.fired",
  "rule": "High error rate",
  "severity": "critical",
  "condition": "error_rate > 0.10",
  "current_value": 0.14,
  "window": "5m",
  "fired_at": "2026-03-17T09:30:00Z"
}
```

---

## agents

Controls agent auto-registration behavior.

```yaml
agents:
  auto_register: true
  default_tags:
    environment: "production"
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `auto_register` | bool | `true` | Automatically register new agents from incoming spans |
| `default_tags` | map | `{}` | Tags applied to all auto-registered agents |

---

## dashboard

Controls the real-time dashboard behavior and chart layout.

```yaml
dashboard:
  refresh_interval_seconds: 5
  default_time_range: "1h"
  charts:
    - type: "token_usage"
      title: "Token consumption"
      position: { row: 1, col: 1, width: 2 }
    - type: "cost_breakdown"
      title: "Cost by agent"
      position: { row: 1, col: 3, width: 1 }
    - type: "latency_percentiles"
      title: "Response latency"
      position: { row: 2, col: 1, width: 1 }
    - type: "error_rate"
      title: "Error rate"
      position: { row: 2, col: 2, width: 1 }
    - type: "tool_success"
      title: "Tool call success"
      position: { row: 2, col: 3, width: 1 }
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `refresh_interval_seconds` | int | `5` | SSE push interval for dashboard updates |
| `default_time_range` | string | `"1h"` | Default time window shown on load |
| `charts[].type` | string | — | Chart type (see below) |
| `charts[].title` | string | — | Display title |
| `charts[].position` | map | — | Grid position: `row`, `col`, `width` |

**Available chart types:** `token_usage`, `cost_breakdown`, `latency_percentiles`,
`error_rate`, `tool_success`, `agent_list`, `trace_list`.

---

## Environment Variables

All secrets should be provided via environment variables rather than hardcoded
in the config file.

| Variable | Description | Config equivalent |
|----------|-------------|-------------------|
| `DATABASE_URL` | Database connection URL | `database.url` |
| `ARGUS_API_KEY` | API authentication key | `security.api_key_auth.key` |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | Used in `webhooks[].url` |

Environment variables take precedence over config file values.

---

## Hot-Reload Behavior

The config watcher monitors `config/argus.yaml` using `watchdog`. When the file
changes:

1. The file is parsed and validated with Pydantic
2. If valid: alert rules and cost models are updated in-place, no restart needed
3. If invalid: the error is logged and the previous config remains active

Changes to `server.host`, `server.port`, and `server.workers` require a server
restart to take effect — all other settings are hot-reloadable.
