"""Tests for API key authentication and rate limiting middleware."""

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


def _make_config(
    tmp_path: Path,
    *,
    api_key: str | None = None,
    api_key_enabled: bool = False,
    rate_limit_enabled: bool = False,
    rate_limit_requests: int = 100,
    rate_limit_window_seconds: int = 60,
) -> Path:
    """Write a config file with security settings and return the path."""
    config: dict[str, Any] = {
        "server": {"host": "0.0.0.0", "port": 8000, "workers": 1, "log_level": "DEBUG"},
        "database": {"url": "sqlite+aiosqlite:///:memory:", "pool_size": 5},
        "ingestion": {
            "otlp_enabled": False,
            "rest_enabled": True,
            "max_batch_size": 100,
            "flush_interval_seconds": 1,
        },
        "metrics": {"aggregation_windows": ["1m"], "retention_days": 7, "snapshot_interval_seconds": 60},
        "cost_model": {"providers": {"openai": {"gpt-4o": {"input": 2.50, "output": 10.00}}}},
        "alerts": {"enabled": False, "check_interval_seconds": 30, "rules": []},
        "agents": {"auto_register": True, "default_tags": {"environment": "test"}},
        "dashboard": {"refresh_interval_seconds": 5, "default_time_range": "1h", "charts": []},
        "security": {
            "api_key_auth": {
                "enabled": api_key_enabled,
                "header_name": "X-API-Key",
            },
            "rate_limiting": {
                "enabled": rate_limit_enabled,
                "requests_per_window": rate_limit_requests,
                "window_seconds": rate_limit_window_seconds,
            },
        },
    }
    if api_key is not None:
        config["security"]["api_key_auth"]["key"] = api_key

    config_path = tmp_path / "argus_security.yaml"
    config_path.write_text(yaml.dump(config))
    return config_path


async def _make_client(
    config_path: Path,
    env_api_key: str | None = None,
) -> AsyncClient:
    """Create a test client with the given config."""
    import argus.models  # noqa: F401

    os.environ["ARGUS_CONFIG_PATH"] = str(config_path)
    if env_api_key is not None:
        os.environ["ARGUS_API_KEY"] = env_api_key
    elif "ARGUS_API_KEY" in os.environ:
        del os.environ["ARGUS_API_KEY"]

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

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
    client = AsyncClient(transport=transport, base_url="http://test")
    # Store engine reference so we can clean up
    client._test_engine = test_engine  # type: ignore[attr-defined]
    return client


# --- API Key Authentication Tests ---


class TestApiKeyAuth:
    """Test API key authentication middleware."""

    @pytest.fixture(autouse=True)
    def _cleanup_env(self) -> None:
        """Clean up env vars after each test."""
        yield  # type: ignore[misc]
        os.environ.pop("ARGUS_API_KEY", None)

    async def test_no_auth_when_disabled(self, tmp_path: Path) -> None:
        """When api_key_auth is disabled, requests succeed without a key."""
        config_path = _make_config(tmp_path, api_key_enabled=False)
        client = await _make_client(config_path)
        try:
            resp = await client.get("/health")
            assert resp.status_code == 200
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]

    async def test_ingestion_requires_api_key(self, tmp_path: Path) -> None:
        """When api_key_auth is enabled, ingestion endpoints require X-API-Key."""
        config_path = _make_config(tmp_path, api_key_enabled=True, api_key="test-secret-key")
        client = await _make_client(config_path)
        try:
            resp = await client.post("/v1/traces", json={"resourceSpans": []})
            assert resp.status_code == 401
            data = resp.json()
            assert "api key" in data["detail"].lower() or "unauthorized" in data["detail"].lower()
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]

    async def test_valid_api_key_accepted(self, tmp_path: Path) -> None:
        """Requests with a valid X-API-Key header succeed."""
        config_path = _make_config(tmp_path, api_key_enabled=True, api_key="test-secret-key")
        client = await _make_client(config_path)
        try:
            resp = await client.post(
                "/v1/traces",
                json={"resourceSpans": []},
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]

    async def test_invalid_api_key_rejected(self, tmp_path: Path) -> None:
        """Requests with an invalid X-API-Key header are rejected."""
        config_path = _make_config(tmp_path, api_key_enabled=True, api_key="test-secret-key")
        client = await _make_client(config_path)
        try:
            resp = await client.post(
                "/v1/traces",
                json={"resourceSpans": []},
                headers={"X-API-Key": "wrong-key"},
            )
            assert resp.status_code == 401
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]

    async def test_health_check_bypasses_auth(self, tmp_path: Path) -> None:
        """Health check endpoint does not require authentication."""
        config_path = _make_config(tmp_path, api_key_enabled=True, api_key="test-secret-key")
        client = await _make_client(config_path)
        try:
            resp = await client.get("/health")
            assert resp.status_code == 200
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]

    async def test_api_key_from_env_var(self, tmp_path: Path) -> None:
        """API key can be set via ARGUS_API_KEY environment variable."""
        config_path = _make_config(tmp_path, api_key_enabled=True)
        client = await _make_client(config_path, env_api_key="env-secret-key")
        try:
            # Without key should fail
            resp = await client.post("/v1/traces", json={"resourceSpans": []})
            assert resp.status_code == 401

            # With key from env should succeed
            resp = await client.post(
                "/v1/traces",
                json={"resourceSpans": []},
                headers={"X-API-Key": "env-secret-key"},
            )
            assert resp.status_code == 200
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]

    async def test_docs_endpoint_bypasses_auth(self, tmp_path: Path) -> None:
        """OpenAPI docs endpoints bypass authentication."""
        config_path = _make_config(tmp_path, api_key_enabled=True, api_key="test-secret-key")
        client = await _make_client(config_path)
        try:
            resp = await client.get("/docs")
            # /docs redirects or returns 200
            assert resp.status_code in (200, 307)
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]


# --- Rate Limiting Tests ---


class TestRateLimiting:
    """Test rate limiting middleware."""

    async def test_no_rate_limit_when_disabled(self, tmp_path: Path) -> None:
        """When rate limiting is disabled, no 429 responses."""
        config_path = _make_config(tmp_path, rate_limit_enabled=False)
        client = await _make_client(config_path)
        try:
            for _ in range(10):
                resp = await client.post("/v1/traces", json={"resourceSpans": []})
                assert resp.status_code == 200
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]

    async def test_rate_limit_enforced(self, tmp_path: Path) -> None:
        """When rate limiting is enabled, exceeding limit returns 429."""
        config_path = _make_config(
            tmp_path, rate_limit_enabled=True, rate_limit_requests=3, rate_limit_window_seconds=60
        )
        client = await _make_client(config_path)
        try:
            # First 3 requests should succeed
            for _ in range(3):
                resp = await client.post("/v1/traces", json={"resourceSpans": []})
                assert resp.status_code == 200

            # 4th request should be rate limited
            resp = await client.post("/v1/traces", json={"resourceSpans": []})
            assert resp.status_code == 429
            data = resp.json()
            assert "rate limit" in data["detail"].lower()
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]

    async def test_rate_limit_does_not_affect_health(self, tmp_path: Path) -> None:
        """Health endpoint is not rate limited."""
        config_path = _make_config(
            tmp_path, rate_limit_enabled=True, rate_limit_requests=2, rate_limit_window_seconds=60
        )
        client = await _make_client(config_path)
        try:
            # Exhaust rate limit on ingestion
            for _ in range(3):
                await client.post("/v1/traces", json={"resourceSpans": []})

            # Health should still work
            resp = await client.get("/health")
            assert resp.status_code == 200
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]

    async def test_rate_limit_header_present(self, tmp_path: Path) -> None:
        """Rate limit response includes Retry-After header."""
        config_path = _make_config(
            tmp_path, rate_limit_enabled=True, rate_limit_requests=1, rate_limit_window_seconds=60
        )
        client = await _make_client(config_path)
        try:
            await client.post("/v1/traces", json={"resourceSpans": []})
            resp = await client.post("/v1/traces", json={"resourceSpans": []})
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers or "retry-after" in resp.headers
        finally:
            await client.aclose()
            await client._test_engine.dispose()  # type: ignore[attr-defined]


# --- Security Module Unit Tests ---


class TestSecurityModule:
    """Test security.py module functions directly."""

    def test_validate_api_key_returns_true_for_valid(self) -> None:
        """validate_api_key returns True for matching key."""
        from argus.core.security import validate_api_key

        assert validate_api_key("my-secret", "my-secret") is True

    def test_validate_api_key_returns_false_for_invalid(self) -> None:
        """validate_api_key returns False for non-matching key."""
        from argus.core.security import validate_api_key

        assert validate_api_key("wrong-key", "my-secret") is False

    def test_validate_api_key_returns_false_for_empty(self) -> None:
        """validate_api_key returns False for empty provided key."""
        from argus.core.security import validate_api_key

        assert validate_api_key("", "my-secret") is False

    def test_is_exempt_path_health(self) -> None:
        """Health endpoint is exempt from auth."""
        from argus.core.security import is_exempt_path

        assert is_exempt_path("/health") is True

    def test_is_exempt_path_docs(self) -> None:
        """Docs endpoints are exempt from auth."""
        from argus.core.security import is_exempt_path

        assert is_exempt_path("/docs") is True
        assert is_exempt_path("/openapi.json") is True

    def test_is_exempt_path_ingestion_not_exempt(self) -> None:
        """Ingestion endpoints are not exempt."""
        from argus.core.security import is_exempt_path

        assert is_exempt_path("/v1/traces") is False

    def test_is_rate_limited_path_ingestion(self) -> None:
        """Ingestion paths are rate-limited."""
        from argus.core.security import is_rate_limited_path

        assert is_rate_limited_path("/v1/traces") is True

    def test_is_rate_limited_path_health(self) -> None:
        """Health endpoint is not rate-limited."""
        from argus.core.security import is_rate_limited_path

        assert is_rate_limited_path("/health") is False
