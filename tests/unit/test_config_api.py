"""Tests for the config API routes and validation."""

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
async def config_client(sample_config: dict[str, Any], tmp_path: Path):
    """Create a test client for config endpoints."""
    import argus.models  # noqa: F401

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


class TestConfigAPI:
    """Test config API endpoints."""

    @pytest.mark.asyncio
    async def test_get_config(self, config_client: AsyncClient) -> None:
        resp = await config_client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "server" in data["config"]

    @pytest.mark.asyncio
    async def test_get_config_yaml(self, config_client: AsyncClient) -> None:
        resp = await config_client.get("/api/v1/config/yaml")
        assert resp.status_code == 200
        data = resp.json()
        assert "yaml" in data
        # Should be valid YAML
        parsed = yaml.safe_load(data["yaml"])
        assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_validate_valid_config(self, config_client: AsyncClient) -> None:
        valid_yaml = yaml.dump(
            {
                "server": {"host": "0.0.0.0", "port": 8000},
                "database": {"url": "sqlite+aiosqlite:///./test.db"},
            }
        )
        resp = await config_client.post(
            "/api/v1/config/validate",
            json={"yaml_content": valid_yaml},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["errors"] == []

    @pytest.mark.asyncio
    async def test_validate_invalid_yaml(self, config_client: AsyncClient) -> None:
        resp = await config_client.post(
            "/api/v1/config/validate",
            json={"yaml_content": "{ invalid yaml: ["},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    @pytest.mark.asyncio
    async def test_validate_invalid_config_structure(self, config_client: AsyncClient) -> None:
        invalid_yaml = yaml.dump(
            {
                "server": {"port": "not-a-number"},
            }
        )
        resp = await config_client.post(
            "/api/v1/config/validate",
            json={"yaml_content": invalid_yaml},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False

    @pytest.mark.asyncio
    async def test_update_config(self, config_client: AsyncClient, sample_config: dict[str, Any]) -> None:
        new_yaml = yaml.dump(sample_config)
        resp = await config_client.post(
            "/api/v1/config",
            json={"yaml_content": new_yaml},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "applied"

    @pytest.mark.asyncio
    async def test_update_config_invalid_rejected(self, config_client: AsyncClient) -> None:
        resp = await config_client.post(
            "/api/v1/config",
            json={"yaml_content": "{ invalid yaml: ["},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_get_audit_log(self, config_client: AsyncClient) -> None:
        resp = await config_client.get("/api/v1/config/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)

    @pytest.mark.asyncio
    async def test_audit_log_records_changes(self, config_client: AsyncClient, sample_config: dict[str, Any]) -> None:
        # Make a config change
        new_yaml = yaml.dump(sample_config)
        await config_client.post(
            "/api/v1/config",
            json={"yaml_content": new_yaml},
        )
        # Check audit log
        resp = await config_client.get("/api/v1/config/audit")
        data = resp.json()
        assert len(data["entries"]) >= 1
        assert data["entries"][0]["action"] == "config_updated"
