---
title: "API Reference"
description: "Complete REST API documentation for Argus Panoptes with curl examples and JSON payloads."
layout: page
---

## Base URL

```
http://localhost:8000
```

All API responses are JSON. Authentication is optional — see [Security]({{ '/configuration' | relative_url }}#security).

---

## Authentication

When API key authentication is enabled, include the key in every request:

```bash
-H "X-API-Key: your-secret-api-key"
```

The header name is configurable via `security.api_key_auth.header_name`.

---

## Health

### GET /health

Returns the service health status. This endpoint is always unauthenticated.

```bash
curl http://localhost:8000/health
```

**Response 200 OK**

```json
{
  "status": "ok",
  "database": "ok",
  "config": "loaded",
  "version": "0.1.0"
}
```

---

## Ingestion

### POST /v1/traces

Ingest OpenTelemetry GenAI Semantic Convention spans. Accepts OTLP/HTTP JSON format.

```bash
curl -X POST http://localhost:8000/v1/traces \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "resourceSpans": [{
      "resource": {
        "attributes": [
          {"key": "gen_ai.agent.name",    "value": {"stringValue": "research-agent"}},
          {"key": "gen_ai.agent.version", "value": {"stringValue": "1.2.0"}},
          {"key": "service.name",         "value": {"stringValue": "my-ai-app"}}
        ]
      },
      "scopeSpans": [{
        "scope": {"name": "argus.sdk", "version": "0.1.0"},
        "spans": [{
          "traceId": "aabbccddeeff00112233445566778899",
          "spanId":  "aabbccddeeff0011",
          "parentSpanId": "",
          "name": "chat gpt-4o",
          "kind": 3,
          "startTimeUnixNano": "1710000000000000000",
          "endTimeUnixNano":   "1710000001200000000",
          "status": {"code": 1},
          "attributes": [
            {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
            {"key": "gen_ai.request.model",  "value": {"stringValue": "gpt-4o"}},
            {"key": "gen_ai.provider.name",  "value": {"stringValue": "openai"}},
            {"key": "gen_ai.usage.input_tokens",  "value": {"intValue": 512}},
            {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 128}},
            {"key": "gen_ai.tool.name",       "value": {"stringValue": "web_search"}},
            {"key": "error.type",             "value": {"stringValue": ""}}
          ]
        }]
      }]
    }]
  }'
```

**Response 200 OK**

```json
{"accepted": 1, "rejected": 0}
```

**Response 422 Unprocessable Entity** — malformed payload

```json
{
  "detail": [
    {"loc": ["body", "resourceSpans"], "msg": "field required", "type": "value_error.missing"}
  ]
}
```

---

## Agents

### GET /api/v1/agents

List all registered agents with their latest metrics snapshot.

```bash
curl http://localhost:8000/api/v1/agents \
  -H "X-API-Key: your-api-key"
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Maximum number of agents to return |
| `offset` | int | 0 | Pagination offset |
| `tag` | string | — | Filter by tag (e.g., `environment:production`) |

**Response 200 OK**

```json
{
  "agents": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "research-agent",
      "version": "1.2.0",
      "first_seen": "2026-03-17T06:00:00Z",
      "last_seen":  "2026-03-17T09:30:00Z",
      "tags": {"environment": "production", "team": "ml"},
      "metrics": {
        "total_spans": 1420,
        "total_tokens": 284000,
        "total_cost_usd": 0.71,
        "error_rate": 0.02,
        "p50_latency_ms": 890,
        "p95_latency_ms": 2400,
        "p99_latency_ms": 5100
      }
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### GET /api/v1/agents/{id}

Get full details for a single agent.

```bash
curl http://localhost:8000/api/v1/agents/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "X-API-Key: your-api-key"
```

**Response 200 OK**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "research-agent",
  "version": "1.2.0",
  "first_seen": "2026-03-17T06:00:00Z",
  "last_seen":  "2026-03-17T09:30:00Z",
  "tags": {"environment": "production"},
  "metrics": {
    "total_spans": 1420,
    "total_tokens": 284000,
    "total_cost_usd": 0.71,
    "error_rate": 0.02,
    "p50_latency_ms": 890,
    "p95_latency_ms": 2400,
    "p99_latency_ms": 5100
  },
  "model_breakdown": {
    "gpt-4o":      {"spans": 900, "tokens": 180000, "cost_usd": 0.54},
    "gpt-4o-mini": {"spans": 520, "tokens": 104000, "cost_usd": 0.17}
  }
}
```

**Response 404 Not Found**

```json
{"detail": "Agent not found"}
```

---

### GET /api/v1/agents/{id}/metrics

Get time-series metrics for an agent across aggregation windows.

```bash
curl "http://localhost:8000/api/v1/agents/a1b2c3d4-e5f6-7890-abcd-ef1234567890/metrics?window=1h" \
  -H "X-API-Key: your-api-key"
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `window` | string | `1h` | Aggregation window: `1m`, `5m`, `1h`, `1d` |
| `from` | ISO8601 | now-1h | Start of time range |
| `to` | ISO8601 | now | End of time range |

**Response 200 OK**

```json
{
  "agent_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "window": "1h",
  "series": [
    {
      "timestamp": "2026-03-17T09:00:00Z",
      "spans":      42,
      "input_tokens":  8400,
      "output_tokens": 2100,
      "cost_usd":      0.023,
      "error_rate":    0.00,
      "p50_ms":        720,
      "p95_ms":        1800
    }
  ]
}
```

---

## Traces

### GET /api/v1/traces

Search traces. Supports pagination and filtering.

```bash
curl "http://localhost:8000/api/v1/traces?agent_id=a1b2c3d4&limit=20" \
  -H "X-API-Key: your-api-key"
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_id` | UUID | — | Filter by agent |
| `limit` | int | 20 | Results per page |
| `offset` | int | 0 | Pagination offset |
| `from` | ISO8601 | now-1h | Start timestamp |
| `to` | ISO8601 | now | End timestamp |
| `model` | string | — | Filter by model name |
| `has_error` | bool | — | Only show traces with errors |
| `min_cost_usd` | float | — | Minimum trace cost |

**Response 200 OK**

```json
{
  "traces": [
    {
      "id": "aabbccddeeff00112233445566778899",
      "agent_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "agent_name": "research-agent",
      "started_at": "2026-03-17T09:30:00Z",
      "ended_at":   "2026-03-17T09:30:01.2Z",
      "duration_ms": 1200,
      "span_count": 3,
      "total_input_tokens": 512,
      "total_output_tokens": 128,
      "total_cost_usd": 0.0016,
      "has_error": false,
      "root_span_name": "chat gpt-4o"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

### GET /api/v1/traces/{id}

Get full trace details including the complete span tree.

```bash
curl http://localhost:8000/api/v1/traces/aabbccddeeff00112233445566778899 \
  -H "X-API-Key: your-api-key"
```

**Response 200 OK**

```json
{
  "id": "aabbccddeeff00112233445566778899",
  "agent_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "agent_name": "research-agent",
  "started_at": "2026-03-17T09:30:00Z",
  "ended_at": "2026-03-17T09:30:01.2Z",
  "duration_ms": 1200,
  "total_cost_usd": 0.0016,
  "spans": [
    {
      "id": "aabbccddeeff0011",
      "parent_id": null,
      "name": "chat gpt-4o",
      "start_time": "2026-03-17T09:30:00Z",
      "end_time": "2026-03-17T09:30:01.2Z",
      "duration_ms": 1200,
      "operation": "chat",
      "model": "gpt-4o",
      "provider": "openai",
      "input_tokens": 512,
      "output_tokens": 128,
      "cost_usd": 0.0016,
      "has_error": false,
      "attributes": {
        "gen_ai.operation.name": "chat",
        "gen_ai.request.model": "gpt-4o",
        "gen_ai.provider.name": "openai"
      },
      "tool_calls": []
    }
  ]
}
```

---

## Metrics

### GET /api/v1/metrics/summary

Get an aggregated summary of all metrics, optionally for a specific time window.

```bash
curl "http://localhost:8000/api/v1/metrics/summary?window=1h" \
  -H "X-API-Key: your-api-key"
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `window` | string | `1h` | One of: `1m`, `5m`, `1h`, `1d` |

**Response 200 OK**

```json
{
  "window": "1h",
  "computed_at": "2026-03-17T09:30:00Z",
  "agents_active": 3,
  "total_spans": 4820,
  "total_input_tokens": 964000,
  "total_output_tokens": 241000,
  "total_cost_usd": 2.89,
  "error_rate": 0.014,
  "p50_latency_ms": 920,
  "p95_latency_ms": 3100,
  "p99_latency_ms": 7200,
  "top_models": [
    {"model": "gpt-4o",      "spans": 2100, "cost_usd": 1.89},
    {"model": "gpt-4o-mini", "spans": 1800, "cost_usd": 0.68},
    {"model": "claude-sonnet-4-6", "spans": 920, "cost_usd": 0.32}
  ]
}
```

---

## Alerts

### GET /api/v1/alerts

List all alert rules and their current status.

```bash
curl http://localhost:8000/api/v1/alerts \
  -H "X-API-Key: your-api-key"
```

**Response 200 OK**

```json
{
  "rules": [
    {
      "name": "High error rate",
      "condition": "error_rate > 0.10",
      "window": "5m",
      "severity": "critical",
      "notify": ["webhook"],
      "status": "ok",
      "last_evaluated": "2026-03-17T09:30:00Z",
      "last_fired": null
    },
    {
      "name": "Cost spike",
      "condition": "cost_usd_per_hour > 50.00",
      "window": "1h",
      "severity": "warning",
      "notify": ["webhook"],
      "status": "firing",
      "last_evaluated": "2026-03-17T09:30:00Z",
      "last_fired": "2026-03-17T09:29:00Z"
    }
  ]
}
```

---

## Configuration

### GET /api/v1/config

Get the current effective configuration (sensitive values redacted).

```bash
curl http://localhost:8000/api/v1/config \
  -H "X-API-Key: your-api-key"
```

**Response 200 OK**

```json
{
  "server": {"host": "0.0.0.0", "port": 8000, "workers": 4, "log_level": "INFO"},
  "database": {"url": "sqlite+aiosqlite:///./argus.db", "pool_size": 10},
  "ingestion": {"otlp_enabled": true, "otlp_port": 4318, "rest_enabled": true, "max_batch_size": 1000},
  "metrics": {"aggregation_windows": ["1m", "5m", "1h", "1d"], "retention_days": 90},
  "security": {"api_key_auth": {"enabled": false, "header_name": "X-API-Key"}},
  "alerts": {"enabled": true, "check_interval_seconds": 30, "rules": []},
  "dashboard": {"refresh_interval_seconds": 5, "default_time_range": "1h"}
}
```

---

### PUT /api/v1/config

Update the running configuration. The config file is written and hot-reloaded.

```bash
curl -X PUT http://localhost:8000/api/v1/config \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "metrics": {
      "retention_days": 30
    },
    "alerts": {
      "enabled": true,
      "check_interval_seconds": 60
    }
  }'
```

**Response 200 OK**

```json
{"status": "updated", "reloaded": true}
```

**Response 400 Bad Request** — invalid config

```json
{"detail": "Invalid configuration: metrics.retention_days must be > 0"}
```

---

## SSE Stream

### GET /api/v1/sse

Server-Sent Events stream for real-time dashboard updates. Each event contains
a partial HTML fragment for HTMX to swap.

```bash
curl -N http://localhost:8000/api/v1/sse \
  -H "Accept: text/event-stream"
```

**Event format**

```
event: metrics_update
data: {"window": "1m", "total_cost_usd": 0.42, "error_rate": 0.01}

event: agent_update
data: {"agent_id": "...", "last_seen": "2026-03-17T09:30:00Z"}
```

---

## Error Codes

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Bad Request — invalid payload or config |
| 401 | Unauthorized — missing or invalid API key |
| 404 | Not Found |
| 422 | Unprocessable Entity — validation error |
| 429 | Too Many Requests — rate limit exceeded |
| 500 | Internal Server Error |
