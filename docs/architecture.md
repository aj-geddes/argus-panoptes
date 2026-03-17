---
title: "Architecture"
description: "System architecture, data flow, component hierarchy, and sequence diagrams for Argus Panoptes."
layout: page
---

## System Overview

Argus Panoptes is structured as a layered FastAPI application. Agent frameworks
emit OpenTelemetry spans, which are ingested, stored, aggregated, and surfaced
through both a REST API and a real-time HTMX frontend.

```mermaid
graph TB
    subgraph Frameworks["Agent Frameworks"]
        LG["LangGraph"]
        CA["CrewAI"]
        OA["OpenAI SDK"]
        CU["Custom Agents"]
    end

    subgraph Ingestion["Ingestion Layer"]
        REST["/v1/traces (REST)"]
        OTLP["OTLP/HTTP :4318"]
    end

    subgraph Core["Argus Core (FastAPI)"]
        IG["Ingestion Service"]
        ME["Metrics Engine"]
        CC["Cost Calculator"]
        AE["Alert Engine"]
        CM["Config Manager"]
        SS["SSE Broadcaster"]
    end

    subgraph Storage["Storage"]
        DB["SQLite / PostgreSQL"]
        MS["MetricSnapshots"]
    end

    subgraph Frontend["Frontend"]
        HX["HTMX + Alpine.js"]
        DA["Dashboard"]
        TR["Trace Explorer"]
        AL["Alerts View"]
        CF["Config Editor"]
    end

    LG -->|OTel spans| REST
    CA -->|OTel spans| REST
    OA -->|OTel spans| REST
    CU -->|SDK| REST

    REST --> IG
    OTLP --> IG
    IG --> ME
    IG --> DB
    ME --> CC
    ME --> MS
    MS --> AE
    CM -->|watchdog| CM
    AE -->|webhooks| WH["Slack / HTTP"]
    SS -->|SSE| HX
    DB --> HX
    HX --> DA
    HX --> TR
    HX --> AL
    HX --> CF
```

---

## Component Hierarchy

```mermaid
graph TD
    APP["argus.main (FastAPI app)"]

    subgraph Routes["Routes"]
        API["routes/api/"]
        VIEWS["routes/views/"]
    end

    subgraph Services["Services"]
        ING["ingestion.py"]
        AGR["agent_registry.py"]
        MET["metrics.py"]
        ALT["alerting.py"]
        TRQ["trace_query.py"]
        CST["cost_calculator.py"]
        WHK["webhooks.py"]
    end

    subgraph Core["Core"]
        CFG["config.py (hot-reload)"]
        DB2["database.py (async engine)"]
        SEC["security.py (API key + rate)"]
        SSE2["sse.py (broadcaster)"]
        UTL["utils.py"]
    end

    subgraph Models["Models"]
        AGM["agent.py"]
        TRM["trace.py"]
        SPM["span.py"]
        TCM["tool_call.py"]
        MSM["metric_snapshot.py"]
    end

    APP --> Routes
    APP --> Core
    Routes --> Services
    Services --> Core
    Services --> Models
    Core --> Models
```

---

## Data Flow: Span Ingestion

```mermaid
sequenceDiagram
    participant C  as Client
    participant AP as /v1/traces
    participant IS as IngestionService
    participant AR as AgentRegistry
    participant ME as MetricsEngine
    participant CC as CostCalculator
    participant DB as Database
    participant SS as SSEBroadcaster

    C->>AP: POST /v1/traces (OTLP JSON)
    AP->>AP: Validate schema (Pydantic)
    AP->>IS: process_spans(resource_spans)
    IS->>AR: get_or_create_agent(name, tags)
    AR->>DB: SELECT / INSERT agent
    DB-->>AR: agent record
    IS->>DB: INSERT trace, spans, tool_calls
    IS->>CC: calculate_cost(model, input_tokens, output_tokens)
    CC-->>IS: cost_usd
    IS->>ME: record_metrics(agent_id, span_data)
    ME->>DB: UPDATE MetricSnapshot (windowed)
    ME->>SS: broadcast_update(metrics_delta)
    SS-->>C: SSE event (dashboard refresh)
    AP-->>C: {"accepted": N, "rejected": 0}
```

---

## Data Flow: STDIO Ingestion (SDK)

```mermaid
sequenceDiagram
    participant AG as Agent Code
    participant SDK as ArgusReporter (SDK)
    participant Q  as AsyncQueue
    participant BG as Background Flush Task
    participant AP as /v1/traces

    AG->>SDK: report_span(operation, model, tokens, ...)
    SDK->>SDK: build_otlp_span()
    SDK->>Q: enqueue(span)

    loop Every flush_interval_seconds
        BG->>Q: drain_queue()
        Q-->>BG: [span_batch]
        BG->>AP: POST /v1/traces (batch)
        AP-->>BG: {"accepted": N}
    end

    Note over AG,SDK: report_span() returns immediately<br/>(non-blocking)
```

---

## Entity-Relationship Diagram

```mermaid
erDiagram
    AGENT {
        uuid    id          PK
        string  name
        string  version
        json    tags
        datetime first_seen
        datetime last_seen
    }

    TRACE {
        string  id          PK
        uuid    agent_id    FK
        datetime started_at
        datetime ended_at
        int     span_count
        float   total_cost_usd
        bool    has_error
    }

    SPAN {
        string  id          PK
        string  trace_id    FK
        string  parent_id
        string  name
        string  operation
        string  model
        string  provider
        int     input_tokens
        int     output_tokens
        float   cost_usd
        int     duration_ms
        bool    has_error
        json    attributes
    }

    TOOL_CALL {
        uuid    id          PK
        string  span_id     FK
        string  name
        json    input
        json    output
        bool    success
        int     duration_ms
    }

    METRIC_SNAPSHOT {
        uuid    id          PK
        uuid    agent_id    FK
        string  window
        datetime computed_at
        int     span_count
        int     input_tokens
        int     output_tokens
        float   cost_usd
        float   error_rate
        float   p50_ms
        float   p95_ms
        float   p99_ms
    }

    AGENT ||--o{ TRACE : "has"
    TRACE ||--o{ SPAN : "contains"
    SPAN  ||--o{ TOOL_CALL : "invokes"
    AGENT ||--o{ METRIC_SNAPSHOT : "aggregates"
```

---

## Configuration Hot-Reload

```mermaid
sequenceDiagram
    participant FS  as Filesystem
    participant WD  as watchdog (file watcher)
    participant CM  as ConfigManager
    participant AE  as AlertEngine
    participant CC  as CostCalculator

    FS->>WD: file modified event (argus.yaml)
    WD->>CM: on_modified(path)
    CM->>CM: reload_config()
    CM->>CM: validate with Pydantic
    alt Valid config
        CM->>AE: update_rules(new_config.alerts.rules)
        CM->>CC: update_pricing(new_config.cost_model)
        CM-->>FS: log "Config reloaded OK"
    else Invalid config
        CM-->>FS: log "Config reload FAILED: {error}"
        Note over CM: Old config remains active
    end
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend framework | FastAPI | Async HTTP, dependency injection, OpenAPI |
| ORM / Models | SQLModel + SQLAlchemy async | Type-safe DB access, migrations |
| Database | SQLite (dev) / PostgreSQL (prod) | Persistent storage |
| Validation | Pydantic v2 | Request/response schemas, config |
| Real-time | Server-Sent Events | Live dashboard updates |
| Config reload | watchdog | File-system event monitoring |
| Frontend | HTMX 2.x + Alpine.js 3.x | Reactive UI without a JS build step |
| Styling | Tailwind CSS 4.x | Utility-first CSS |
| Migrations | Alembic | Schema evolution for SQLite + PostgreSQL |
| Container | Docker multi-stage | Minimal image, non-root user |
| CI | GitHub Actions | Lint, type check, security scan, tests |

---

## Design Principles

1. **API routes return JSON, view routes return HTML.** Never mix them. This keeps
   the REST API clean and independently usable.

2. **HTMX targets fragments.** Each `hx-get` targets a route that returns exactly
   the HTML partial it needs to swap. No full-page reloads.

3. **Hot-reload is foundational.** The `ConfigManager` watches `argus.yaml` with
   watchdog. Invalid YAML is rejected, the old config stays active.

4. **Dual database support.** All SQL uses SQLAlchemy Core / SQLModel — no raw
   SQL. Alembic uses `render_as_batch=True` for SQLite `ALTER TABLE` compatibility.

5. **Type everything.** All function signatures have type hints. mypy strict mode
   is enforced in CI.

6. **Cost is always calculated server-side.** Clients never send cost — Argus
   always derives cost from token counts and the config-driven pricing table.
