---
title: "Changelog"
description: "Version history and release notes for Argus Panoptes."
layout: page
---

All notable changes to Argus Panoptes are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_Changes in development, not yet released._

---

## [0.1.0] — 2026-03-17

Initial release of Argus Panoptes.

### Added

**Core platform**
- FastAPI application with async SQLAlchemy/SQLModel data layer
- OpenTelemetry GenAI Semantic Conventions v1.37 ingestion endpoint (`POST /v1/traces`)
- Agent auto-registration from incoming spans
- Trace and span storage with tool call tracking

**Metrics and cost tracking**
- Windowed metrics aggregation engine (1m, 5m, 1h, 1d windows)
- Config-driven per-token cost calculator for OpenAI, Anthropic, Google, DeepSeek, xAI, Mistral, and Meta models
- Pre-aggregated MetricSnapshot model for fast dashboard rendering
- Real-time metrics summary API

**Dashboard and visualization**
- HTMX + Alpine.js + Tailwind CSS frontend (zero JS build step)
- Server-Sent Events (SSE) for live dashboard updates
- Agent list, agent detail, and trace explorer views
- Searchable trace list with span tree visualization

**Alerting**
- Rule-based alert engine with configurable conditions and severity levels
- Webhook notification system (Slack, etc.)
- Alert history and status tracking

**Configuration**
- YAML-based configuration with watchdog hot-reload (zero-downtime changes)
- In-browser config editor with validation
- Config change audit logging

**Security**
- API key authentication for ingestion endpoints (optional, configurable)
- Per-client rate limiting on ingestion endpoints
- Constant-time API key comparison to prevent timing attacks

**Database**
- SQLite support for development (default, zero setup)
- PostgreSQL support for production (asyncpg driver)
- Alembic migrations compatible with both SQLite and PostgreSQL
- `DATABASE_URL` environment variable support

**Infrastructure**
- Multi-stage Docker build with non-root user and health checks
- Docker Compose for development with hot-reload
- GitHub Actions CI: Ruff lint, mypy type check, bandit security scan, pytest
- GitHub Actions CD: Docker build and push to GHCR on tag

**SDK**
- Python SDK shim (`argus.sdk.reporter.ArgusReporter`) for frameworks without native OTel support
- Async batching, configurable flush interval, context manager support

**Documentation**
- GitHub Pages documentation site (this site)
- Comprehensive README with quickstart guide
- CONTRIBUTING.md with development setup and PR process
- SECURITY.md with vulnerability reporting guidelines
- Apache 2.0 LICENSE

---

[Unreleased]: https://github.com/aj-geddes/argus-panoptes/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aj-geddes/argus-panoptes/releases/tag/v0.1.0
