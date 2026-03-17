"""Shared test fixtures for Argus Panoptes."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

os.environ["ARGUS_CONFIG_PATH"] = ""  # Will be overridden per-test


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def sample_config() -> dict[str, Any]:
    """Return a minimal valid config dict for testing."""
    return {
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "workers": 1,
            "log_level": "DEBUG",
        },
        "database": {
            "url": "sqlite+aiosqlite:///:memory:",
            "pool_size": 5,
        },
        "ingestion": {
            "otlp_enabled": False,
            "rest_enabled": True,
            "max_batch_size": 100,
            "flush_interval_seconds": 1,
        },
        "metrics": {
            "aggregation_windows": ["1m", "5m"],
            "retention_days": 7,
            "snapshot_interval_seconds": 60,
        },
        "cost_model": {
            "providers": {
                "openai": {
                    "gpt-4o": {"input": 2.50, "output": 10.00},
                },
                "anthropic": {
                    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
                },
            },
        },
        "alerts": {"enabled": False, "check_interval_seconds": 30, "rules": []},
        "agents": {"auto_register": True, "default_tags": {"environment": "test"}},
        "dashboard": {
            "refresh_interval_seconds": 5,
            "default_time_range": "1h",
            "charts": [],
        },
    }


@pytest.fixture()
def config_file(sample_config: dict[str, Any], tmp_path: Path) -> Path:
    """Write sample config to a temporary YAML file and return its path."""
    config_path = tmp_path / "argus.yaml"
    config_path.write_text(yaml.dump(sample_config))
    return config_path


@pytest.fixture()
async def async_engine():
    """Create an async SQLite in-memory engine for testing."""
    # Import all models so they register with SQLModel.metadata before create_all
    import argus.models  # noqa: F401

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture()
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create an async session for testing with expire_on_commit=False."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture()
async def app_client(config_file: Path, tmp_path: Path):
    """Create a test client for the FastAPI app with an in-memory database."""
    import argus.models  # noqa: F401

    os.environ["ARGUS_CONFIG_PATH"] = str(config_file)

    # Create a test engine with in-memory SQLite
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Override the get_session dependency
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    from argus.main import create_app

    app = create_app(config_path=str(config_file))

    # Override the database dependency
    from argus.core.database import get_session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Cleanup
    await test_engine.dispose()
    app.dependency_overrides.clear()
