# Argus Panoptes

**The all-seeing eye for your AI agents.**

Unified observability platform for AI agent frameworks. Track performance, costs, and behavior across LangGraph, CrewAI, OpenAI Agents SDK, Google ADK, and any framework that emits OpenTelemetry spans.

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the app
uvicorn argus.main:app --reload --reload-dir src

# Run tests
pytest --cov
```

## Docker

```bash
cd docker
docker compose up
```

Open http://localhost:8000 to view the dashboard.

## Configuration

Edit `config/argus.yaml` — changes are applied live without restart.

## License

Apache 2.0
