---
title: "Argus Panoptes — AI Agent Observability"
description: "The all-seeing eye for your AI agents. Self-hosted observability for LangGraph, CrewAI, OpenAI, and any OTel-compatible framework."
layout: default
---
<div class="content-wrapper">

<!-- Hero -->
<section class="hero">
  <div class="hero-eyebrow">v0.1.0 — Now Available</div>
  <h1 class="hero-title">
    The all-seeing eye for<br>
    <span class="highlight">your AI agents.</span>
  </h1>
  <p class="hero-description">
    Argus Panoptes is a self-hosted, framework-agnostic observability platform for AI agents.
    Track tokens, costs, latency, and errors across LangGraph, CrewAI, OpenAI, and any
    framework that emits OpenTelemetry GenAI spans.
  </p>
  <div class="hero-actions">
    <a href="{{ '/getting-started' | relative_url }}" class="btn btn-primary">Get Started</a>
    <a href="{{ '/api-reference' | relative_url }}" class="btn btn-outline">API Reference</a>
    <a href="https://github.com/aj-geddes/argus-panoptes" class="btn btn-outline" target="_blank" rel="noopener">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
      View on GitHub
    </a>
  </div>
</section>

<!-- Feature Cards -->
<div class="feature-grid">
  <div class="feature-card">
    <div class="feature-card-icon">&#9673;</div>
    <div class="feature-card-title">Framework-Agnostic Ingestion</div>
    <div class="feature-card-desc">Accepts OpenTelemetry GenAI Semantic Conventions v1.37 spans via REST. Works with any OTEL-compatible framework out of the box.</div>
  </div>
  <div class="feature-card">
    <div class="feature-card-icon">&#36;</div>
    <div class="feature-card-title">Real-Time Cost Tracking</div>
    <div class="feature-card-desc">Automatic per-token cost calculation for OpenAI, Anthropic, Google, DeepSeek, xAI, Mistral, and Meta models. Config-driven pricing.</div>
  </div>
  <div class="feature-card">
    <div class="feature-card-icon">&#9654;</div>
    <div class="feature-card-title">Live Dashboard via SSE</div>
    <div class="feature-card-desc">Real-time metrics via Server-Sent Events. HTMX + Alpine.js frontend — zero JS build step, under 31KB total JavaScript.</div>
  </div>
  <div class="feature-card">
    <div class="feature-card-icon">&#9883;</div>
    <div class="feature-card-title">Trace Visualization</div>
    <div class="feature-card-desc">Searchable trace explorer with full span tree rendering. Inspect every LLM call, tool invocation, and agent step.</div>
  </div>
  <div class="feature-card">
    <div class="feature-card-icon">&#9888;</div>
    <div class="feature-card-title">Configurable Alerting</div>
    <div class="feature-card-desc">Rule-based alerts on error rate, cost spikes, latency, and more. Webhook notifications for Slack, PagerDuty, or any HTTP endpoint.</div>
  </div>
  <div class="feature-card">
    <div class="feature-card-icon">&#9851;</div>
    <div class="feature-card-title">Hot-Reload Configuration</div>
    <div class="feature-card-desc">Edit <code>config/argus.yaml</code> and changes apply instantly via watchdog. Zero downtime, no restarts required.</div>
  </div>
  <div class="feature-card">
    <div class="feature-card-icon">&#128195;</div>
    <div class="feature-card-title">Dual Database Support</div>
    <div class="feature-card-desc">SQLite for local development (zero setup). PostgreSQL for production. Same codebase, switch via one config line.</div>
  </div>
  <div class="feature-card">
    <div class="feature-card-icon">&#128274;</div>
    <div class="feature-card-title">Security Built-In</div>
    <div class="feature-card-desc">Optional API key authentication, per-client rate limiting, constant-time key comparison, and non-root Docker container.</div>
  </div>
</div>

---

## Quick Start

Up and running in under two minutes with Docker:

```bash
git clone https://github.com/aj-geddes/argus-panoptes.git
cd argus-panoptes/docker
docker compose up
```

Open [http://localhost:8000](http://localhost:8000) — the dashboard is live.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, SQLModel, SQLAlchemy async |
| Frontend | HTMX 2.x, Alpine.js 3.x, Tailwind CSS 4.x |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Real-time | Server-Sent Events (SSE) |
| Config | YAML with watchdog hot-reload |
| Container | Docker multi-stage, non-root |

---

## Supported Frameworks

| Framework | Integration |
|-----------|-------------|
| LangGraph / LangChain | `OTEL_EXPORTER_OTLP_ENDPOINT` env var |
| CrewAI | Native OTel instrumentation |
| OpenAI Agents SDK | OTel Python SDK or Argus SDK shim |
| Google ADK | OTel collector |
| PydanticAI | Native OTel support |
| AutoGen | `opentelemetry-instrumentation-autogen` |
| Custom agents | REST API or [Python SDK]({{ '/sdk' | relative_url }}) |

</div>
