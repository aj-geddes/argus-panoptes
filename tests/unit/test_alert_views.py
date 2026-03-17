"""Tests for alert dashboard and config editor views."""

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
async def view_client(sample_config: dict[str, Any], tmp_path: Path):
    """Create a test client for view endpoints."""
    import argus.models  # noqa: F401

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
        ],
    }

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


class TestAlertDashboardView:
    """Test alert dashboard HTML view."""

    @pytest.mark.asyncio
    async def test_alerts_page_returns_html(self, view_client: AsyncClient) -> None:
        resp = await view_client.get("/alerts")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_alerts_page_contains_rules(self, view_client: AsyncClient) -> None:
        resp = await view_client.get("/alerts")
        assert resp.status_code == 200
        assert "High error rate" in resp.text

    @pytest.mark.asyncio
    async def test_alerts_page_contains_history_section(self, view_client: AsyncClient) -> None:
        resp = await view_client.get("/alerts")
        assert resp.status_code == 200
        assert "Alert History" in resp.text or "history" in resp.text.lower()


class TestConfigEditorView:
    """Test config editor HTML view."""

    @pytest.mark.asyncio
    async def test_config_page_returns_html(self, view_client: AsyncClient) -> None:
        resp = await view_client.get("/config")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_config_page_contains_editor(self, view_client: AsyncClient) -> None:
        resp = await view_client.get("/config")
        assert resp.status_code == 200
        assert "config" in resp.text.lower()

    @pytest.mark.asyncio
    async def test_config_page_contains_save_button(self, view_client: AsyncClient) -> None:
        resp = await view_client.get("/config")
        assert resp.status_code == 200
        assert "Save" in resp.text or "save" in resp.text.lower()

    @pytest.mark.asyncio
    async def test_config_update_via_form(self, view_client: AsyncClient, sample_config: dict[str, Any]) -> None:
        config_yaml = yaml.dump(sample_config)
        resp = await view_client.post(
            "/config/update",
            data={"config_yaml": config_yaml},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_config_update_invalid_yaml(self, view_client: AsyncClient) -> None:
        resp = await view_client.post(
            "/config/update",
            data={"config_yaml": "{ invalid yaml: ["},
        )
        assert resp.status_code == 200
        # Should show error message
        assert "error" in resp.text.lower() or "invalid" in resp.text.lower()


@pytest.fixture()
async def view_client_with_agent(sample_config: dict[str, Any], tmp_path: Path):
    """Create a test client with a pre-seeded agent for detail page testing."""
    import argus.models  # noqa: F401
    from argus.models.agent import Agent

    sample_config["alerts"] = {
        "enabled": True,
        "check_interval_seconds": 30,
        "rules": [],
    }

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

    # Seed an agent
    async with test_session_factory() as session:
        agent = Agent(id="test-agent-id", name="test-agent", framework="custom")
        session.add(agent)
        await session.commit()

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


class TestAgentDetailView:
    """Test agent detail HTML view."""

    @pytest.mark.asyncio
    async def test_agent_detail_not_found(self, view_client: AsyncClient) -> None:
        resp = await view_client.get("/agents/nonexistent/detail")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_agents_list_page(self, view_client: AsyncClient) -> None:
        resp = await view_client.get("/agents")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_agent_detail_found(self, view_client_with_agent: AsyncClient) -> None:
        resp = await view_client_with_agent.get("/agents/test-agent-id/detail")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "test-agent" in resp.text

    @pytest.mark.asyncio
    async def test_agent_detail_contains_metrics(self, view_client_with_agent: AsyncClient) -> None:
        resp = await view_client_with_agent.get("/agents/test-agent-id/detail")
        assert resp.status_code == 200
        assert "Traces" in resp.text
        assert "Tokens" in resp.text
        assert "Cost" in resp.text

    @pytest.mark.asyncio
    async def test_agents_list_shows_agents(self, view_client_with_agent: AsyncClient) -> None:
        resp = await view_client_with_agent.get("/agents")
        assert resp.status_code == 200
        assert "test-agent" in resp.text
