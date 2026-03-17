---
title: "User Guide"
description: "Walkthrough of the Argus Panoptes dashboard, trace explorer, alerts, and config editor."
layout: page
---

## Dashboard

The main dashboard is available at `http://localhost:8000`. It displays a live
view of all active agents and key metrics, refreshed every 5 seconds via SSE.

### Metric Cards

The top row shows four summary metrics for the selected time window:

| Card | Description |
|------|-------------|
| **Total Tokens** | Input + output tokens across all agents |
| **Total Cost** | USD cost for the selected time window |
| **Error Rate** | Fraction of spans that resulted in errors |
| **P95 Latency** | 95th percentile response time in ms |

### Time Window Selector

Use the time picker in the top-right corner to change the aggregation window:
`1m`, `5m`, `1h`, `1d`. The entire dashboard updates immediately.

### Agent List

Below the metric cards, the agent list shows each registered agent with:
- Agent name and version
- Last seen timestamp
- Span count and token usage for the selected window
- Cost for the window
- Error rate (color-coded: green < 5%, amber 5–10%, red > 10%)

Click any agent row to open the agent detail view.

---

## Agent Detail

The agent detail page shows per-agent metrics and the trace list for that agent.

### Model Breakdown

A table showing token consumption and cost split by LLM model. Useful for
understanding which models are driving your costs.

### Metrics Charts

- **Token Usage** — input vs output tokens over time
- **Cost Trend** — cost per window
- **Latency Percentiles** — P50, P95, P99 over time
- **Error Rate** — error fraction over time

---

## Trace Explorer

Navigate to `/traces` (or click **Traces** in the sidebar) to search and
browse all ingested traces.

### Search and Filter

| Filter | Description |
|--------|-------------|
| Agent | Filter by agent name |
| Time range | Custom start/end time |
| Model | Filter by LLM model |
| Has error | Show only traces with errors |
| Min cost | Minimum trace cost in USD |

### Trace List

Each row shows:
- Trace ID (truncated)
- Agent name
- Root span name (e.g., `chat gpt-4o`)
- Start time
- Duration
- Token count
- Cost
- Error indicator

### Trace Detail

Click any trace to open the span tree view. The tree shows:
- Each span as a row with indentation indicating parent-child relationships
- Duration bar (relative to total trace duration)
- Token counts and cost per span
- Tool calls nested under their parent span
- Error badges on failing spans

Click any span to expand its raw attributes.

---

## Alerts

Navigate to `/alerts` to manage alert rules.

### Alert Status

Active alert rules are listed with:
- Rule name
- Condition expression
- Current status: **OK** (green), **Firing** (red), **Unknown** (amber)
- Last evaluated timestamp
- Last fired timestamp

### Firing Alerts

When an alert fires, it appears at the top of the page in a red card with the
current value and the threshold. Alerts auto-resolve when the condition is no
longer true.

### Configuring Alerts

Edit `config/argus.yaml` to add or modify alert rules. Changes are hot-reloaded
within the `check_interval_seconds` cycle.

See [Configuration]({{ '/configuration' | relative_url }}#alerts) for the full
alert rule syntax.

---

## Config Editor

Navigate to `/config` to view and edit the running configuration in-browser.

### YAML Editor

The editor shows the full `argus.yaml` content with syntax highlighting. To
update the config:

1. Make your changes in the editor
2. Click **Validate** — the server checks the YAML without applying it
3. Click **Save** — the config is written and hot-reloaded

Invalid YAML is rejected with an inline error message. The server never
enters an invalid state.

### Config Sections

The sidebar shows a summary of key config values:
- Database URL (redacted)
- API auth status (enabled/disabled)
- Alert rules count
- Cost model provider count

---

## Real-Time Updates

Argus uses Server-Sent Events (SSE) to push updates to the dashboard without
polling. The connection is established automatically when you open any
dashboard page.

If the SSE connection is lost (e.g., network interruption), the UI shows a
"Reconnecting..." indicator and automatically re-connects with exponential
backoff.

To disable real-time updates for testing, set:

```yaml
dashboard:
  refresh_interval_seconds: 0
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `G D` | Go to Dashboard |
| `G T` | Go to Traces |
| `G A` | Go to Agents |
| `/` | Focus search |
| `Esc` | Close modal / clear search |

---

## Tips

**Comparing agents**: Open two agent detail pages in separate tabs to compare
cost and latency profiles side by side.

**Spotting regressions**: Use the `1d` time window and look for step changes in
the latency P95 chart. A sudden increase usually indicates a prompt change or
new model version.

**Cost alerts**: Set a `cost_usd_per_hour` alert at a threshold slightly above
your typical spend to catch runaway agent loops early.

**Tool call debugging**: The span tree shows tool call success/failure for each
invocation. High tool failure rates often indicate API key issues or rate limits
in downstream services.
