---
title: "Contributing"
description: "Development setup, code style, testing requirements, and pull request process for Argus Panoptes."
layout: page
---

Thank you for your interest in contributing to Argus Panoptes! This guide covers
everything you need to get started.

---

## Development Setup

### Prerequisites

- Python 3.12 or later
- Git
- Docker and Docker Compose (optional, for containerized development)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/aj-geddes/argus-panoptes.git
cd argus-panoptes

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# Install with development dependencies
pip install -e ".[dev]"

# Copy the example config
cp config/argus.example.yaml config/argus.yaml

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn argus.main:app --reload --reload-dir src

# Run the test suite
pytest --cov
```

### Docker Setup

```bash
cd docker
docker compose up
```

This starts the app with hot-reload and a Tailwind CSS watcher.

---

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting.

### Key rules

- **Line length**: 120 characters
- **Quotes**: double quotes
- **Imports**: sorted by isort rules, `argus` as first-party
- **Type hints**: required on all function signatures (mypy strict mode)
- **Docstrings**: required for public modules, classes, and functions

### Commands

```bash
# Lint
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/argus/

# Security scan
bandit -r src/argus/ -c pyproject.toml
```

---

## Testing

We use [pytest](https://docs.pytest.org/) with
[pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) for async tests.

### Running tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/argus --cov-report=term-missing

# Run a specific test file
pytest tests/unit/test_security.py -v

# Run tests matching a pattern
pytest -k "test_api_key"
```

### Writing tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use the fixtures from `tests/conftest.py` (`app_client`, `async_session`)
- **Write tests FIRST (TDD)** when implementing new features
- Aim for >80% code coverage on new code

### Test structure

```python
"""Tests for [module name]."""

from __future__ import annotations

import pytest


class TestFeatureName:
    """Test [feature description]."""

    async def test_expected_behavior(self, app_client) -> None:
        """[Describe what the test verifies]."""
        resp = await app_client.get("/endpoint")
        assert resp.status_code == 200
```

---

## Architecture

### Project layout

| Directory | Purpose |
|-----------|---------|
| `src/argus/core/` | Framework-level: config, database, SSE, security |
| `src/argus/models/` | SQLModel database models |
| `src/argus/routes/api/` | REST API route handlers (return JSON) |
| `src/argus/routes/views/` | HTMX view route handlers (return HTML partials) |
| `src/argus/services/` | Business logic layer |
| `src/argus/schemas/` | Pydantic request/response schemas |
| `sdk/python/` | Standalone Python SDK package |
| `docs/` | Jekyll documentation site |

### Key design principles

1. **API routes return JSON, view routes return HTML** — never mix them
2. **HTMX targets partials** — each `hx-get` hits a route that returns a fragment
3. **Hot-reload is foundational** — `ConfigManager` watches `config/argus.yaml`
4. **Dual database support** — code must work with SQLite and PostgreSQL
5. **Type everything** — all signatures have type hints, mypy strict mode

---

## Pull Request Process

1. **Fork and branch** — create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Write tests first** — add failing tests before implementing features (TDD)

3. **Implement the change** — keep PRs focused on a single concern

4. **Ensure quality**:
   ```bash
   ruff check src/ tests/
   ruff format --check src/ tests/
   mypy src/argus/
   pytest --cov
   ```

5. **Write a clear commit message** using conventional commits:
   - `feat: add API key authentication for ingestion endpoints`
   - `fix: correct token count aggregation for multi-span traces`
   - `docs: add architecture Mermaid diagrams`
   - `chore: upgrade FastAPI to 0.115`
   - `refactor: extract cost calculation to dedicated service`
   - `test: add coverage for rate limiting edge cases`

6. **Open a PR** with:
   - A description of what changed and why
   - Link to any related issues
   - Screenshots for UI changes

7. **Address review feedback** — push new commits (do not force-push to open PRs)

---

## Reporting Issues

- Use the [GitHub issue tracker](https://github.com/aj-geddes/argus-panoptes/issues)
- **Bugs**: include steps to reproduce, expected vs. actual behavior, and environment
- **Features**: describe the use case and proposed solution
- **Security vulnerabilities**: see [SECURITY.md](https://github.com/aj-geddes/argus-panoptes/blob/main/SECURITY.md)

---

## License

By contributing, you agree that your contributions will be licensed under the
Apache License 2.0.
