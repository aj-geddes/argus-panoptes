"""Tests for the dashboard view route."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_dashboard_returns_html(app_client) -> None:
    """GET / should return an HTML page with dashboard content."""
    response = await app_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Argus" in response.text
    assert "Dashboard" in response.text


@pytest.mark.asyncio
async def test_dashboard_shows_metric_cards(app_client) -> None:
    """Dashboard should display metric cards for agents, traces, and spans."""
    response = await app_client.get("/")
    assert response.status_code == 200
    assert "Registered Agents" in response.text
    assert "Total Traces" in response.text
    assert "Total Spans" in response.text


@pytest.mark.asyncio
async def test_dashboard_shows_empty_state(app_client) -> None:
    """Dashboard with no data should show the empty state message."""
    response = await app_client.get("/")
    assert response.status_code == 200
    assert "No spans ingested yet" in response.text


@pytest.mark.asyncio
async def test_dashboard_after_ingestion(app_client) -> None:
    """Dashboard should show ingested spans after data is sent."""
    # First, ingest some data
    payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "gen_ai.agent.name",
                            "value": {"stringValue": "dashboard-test-agent"},
                        }
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "dash-trace-001",
                                "spanId": "dash-span-001",
                                "name": "chat gpt-4o",
                                "attributes": [
                                    {
                                        "key": "gen_ai.operation.name",
                                        "value": {"stringValue": "chat"},
                                    },
                                    {
                                        "key": "gen_ai.request.model",
                                        "value": {"stringValue": "gpt-4o"},
                                    },
                                ],
                                "startTimeUnixNano": "1710000000000000000",
                                "endTimeUnixNano": "1710000001000000000",
                            }
                        ]
                    }
                ],
            }
        ]
    }
    ingest_response = await app_client.post("/v1/traces", json=payload)
    assert ingest_response.status_code == 200

    # Now check the dashboard
    response = await app_client.get("/")
    assert response.status_code == 200
    # Should show at least 1 span
    assert "chat" in response.text
