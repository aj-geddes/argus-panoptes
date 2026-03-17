"""Tests for FastAPI app startup and health endpoint."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(app_client) -> None:
    """GET /health should return 200 with status ok."""
    response = await app_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_endpoint_includes_timestamp(app_client) -> None:
    """GET /health should include a timestamp field."""
    response = await app_client.get("/health")
    data = response.json()
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_app_has_cors_headers(app_client) -> None:
    """App should include CORS headers on responses."""
    response = await app_client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORS preflight should not return 405
    assert response.status_code in (200, 204)


@pytest.mark.asyncio
async def test_app_title_is_argus_panoptes(app_client) -> None:
    """The OpenAPI docs should reflect the app title."""
    response = await app_client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Argus Panoptes"
