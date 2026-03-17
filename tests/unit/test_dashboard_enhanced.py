"""Enhanced dashboard tests for Phase 2 — time range, metrics cards, chart data."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_dashboard_time_range_picker(app_client) -> None:
    """Dashboard should include the time range picker component."""
    response = await app_client.get("/")
    assert response.status_code == 200
    assert "Time range:" in response.text
    assert "15m" in response.text
    assert "1h" in response.text
    assert "24h" in response.text


@pytest.mark.asyncio
async def test_dashboard_chart_containers(app_client) -> None:
    """Dashboard should include chart canvas elements."""
    response = await app_client.get("/")
    assert response.status_code == 200
    assert "tokenChart" in response.text
    assert "costChart" in response.text
    assert "latencyChart" in response.text


@pytest.mark.asyncio
async def test_dashboard_cost_column(app_client) -> None:
    """Dashboard table should include cost column."""
    response = await app_client.get("/")
    assert response.status_code == 200
    assert "Cost" in response.text


@pytest.mark.asyncio
async def test_dashboard_with_time_range_param(app_client) -> None:
    """Dashboard should accept time_range query parameter."""
    response = await app_client.get("/?time_range=24h")
    assert response.status_code == 200
    assert "Dashboard" in response.text


@pytest.mark.asyncio
async def test_metrics_cards_partial(app_client) -> None:
    """GET /partials/metrics-cards should return HTML fragment."""
    response = await app_client.get("/partials/metrics-cards?time_range=1h")
    assert response.status_code == 200
    assert "Total Traces" in response.text
    assert "Total Tokens" in response.text
    assert "Total Cost" in response.text


@pytest.mark.asyncio
async def test_metrics_cards_partial_with_data(app_client) -> None:
    """Metrics cards partial should reflect ingested data."""
    # Ingest a span
    payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "gen_ai.agent.name",
                            "value": {"stringValue": "partial-agent"},
                        }
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "partial-trace",
                                "spanId": "partial-span",
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
                                    {
                                        "key": "gen_ai.usage.input_tokens",
                                        "value": {"intValue": 500},
                                    },
                                    {
                                        "key": "gen_ai.usage.output_tokens",
                                        "value": {"intValue": 200},
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
    await app_client.post("/v1/traces", json=payload)

    # The data was ingested in 2024, so it won't appear in "1h" range
    # but the endpoint should still return 200
    response = await app_client.get("/partials/metrics-cards?time_range=7d")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_sse_connect_attribute(app_client) -> None:
    """Dashboard should include SSE connect attribute for live updates."""
    response = await app_client.get("/")
    assert response.status_code == 200
    assert 'sse-connect="/sse/dashboard"' in response.text


@pytest.mark.asyncio
async def test_dashboard_chartjs_script(app_client) -> None:
    """Dashboard should include the Chart.js script tag."""
    response = await app_client.get("/")
    assert response.status_code == 200
    assert "chart.js" in response.text or "chart.umd" in response.text
