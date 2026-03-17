"""Tests for the alerts API routes."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel


@pytest.fixture()
async def alerts_client(sample_config: dict[str, Any], tmp_path: Path):
    """Create a test client with alert rules configured."""
    import argus.models  # noqa: F401

    # Enable alerts with rules
    sample_config["alerts"] = {
        "enabled": True,
        "check_interval_seconds": 30,
        "rules": [
            {
                "name": "High error rate",
                "condition": "error_rate > 0.10",
                "window": "5m",
                "severity": "critical",
                "notify": ["webhook"],
            },
            {
                "name": "Cost spike",
                "condition": "cost_usd_per_hour > 50.00",
                "window": "1h",
                "severity": "warning",
                "notify": ["webhook"],
            },
        ],
    }
    sample_config["webhooks"] = [
        {
            "name": "slack-alerts",
            "url": "https://hooks.slack.com/test",
            "events": ["alert.fired", "alert.resolved"],
        },
    ]

    config_path = tmp_path / "argus.yaml"
    config_path.write_text(yaml.dump(sample_config))
    os.environ["ARGUS_CONFIG_PATH"] = str(config_path)

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    from argus.main import create_app

    app = create_app(config_path=str(config_path))

    from argus.core.database import get_session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await test_engine.dispose()
    app.dependency_overrides.clear()


class TestAlertsAPI:
    """Test alert API endpoints."""

    @pytest.mark.asyncio
    async def test_list_alert_rules(self, alerts_client: AsyncClient) -> None:
        resp = await alerts_client.get("/api/v1/alerts/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
        assert len(data["rules"]) == 2
        assert data["rules"][0]["name"] == "High error rate"

    @pytest.mark.asyncio
    async def test_get_alert_history(self, alerts_client: AsyncClient) -> None:
        resp = await alerts_client.get("/api/v1/alerts/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert isinstance(data["events"], list)

    @pytest.mark.asyncio
    async def test_get_alert_history_with_limit(self, alerts_client: AsyncClient) -> None:
        resp = await alerts_client.get("/api/v1/alerts/history?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data

    @pytest.mark.asyncio
    async def test_check_alerts_endpoint(self, alerts_client: AsyncClient) -> None:
        resp = await alerts_client.post("/api/v1/alerts/check")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "metrics" in data
