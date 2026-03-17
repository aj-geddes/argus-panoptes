"""Tests for metrics and agent API routes."""

from __future__ import annotations

import pytest


def _make_span_payload(
    agent_name: str = "api-agent",
    trace_id: str = "api-trace",
    span_id: str = "api-span",
    model: str = "gpt-4o",
    provider: str = "openai",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> dict:
    """Create a minimal OTLP ingest payload."""
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "gen_ai.agent.name",
                            "value": {"stringValue": agent_name},
                        }
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": span_id,
                                "name": f"chat {model}",
                                "attributes": [
                                    {
                                        "key": "gen_ai.operation.name",
                                        "value": {"stringValue": "chat"},
                                    },
                                    {
                                        "key": "gen_ai.request.model",
                                        "value": {"stringValue": model},
                                    },
                                    {
                                        "key": "gen_ai.provider.name",
                                        "value": {"stringValue": provider},
                                    },
                                    {
                                        "key": "gen_ai.usage.input_tokens",
                                        "value": {"intValue": input_tokens},
                                    },
                                    {
                                        "key": "gen_ai.usage.output_tokens",
                                        "value": {"intValue": output_tokens},
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


@pytest.mark.asyncio
async def test_list_agents_empty(app_client) -> None:
    """GET /api/v1/agents should return empty list when no agents exist."""
    response = await app_client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.json()
    assert data["agents"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_agents_with_data(app_client) -> None:
    """GET /api/v1/agents should return agents after ingestion."""
    await app_client.post(
        "/v1/traces",
        json=_make_span_payload(agent_name="agent-alpha", span_id="sp1"),
    )
    response = await app_client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    names = [a["name"] for a in data["agents"]]
    assert "agent-alpha" in names


@pytest.mark.asyncio
async def test_get_agent_detail(app_client) -> None:
    """GET /api/v1/agents/{id} should return agent details."""
    # First ingest to create agent
    await app_client.post(
        "/v1/traces",
        json=_make_span_payload(agent_name="detail-agent", span_id="sp2"),
    )
    # Get agents list to find the id
    agents_resp = await app_client.get("/api/v1/agents")
    agents = agents_resp.json()["agents"]
    agent_id = next(a["id"] for a in agents if a["name"] == "detail-agent")

    # Get detail
    response = await app_client.get(f"/api/v1/agents/{agent_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "detail-agent"


@pytest.mark.asyncio
async def test_get_agent_not_found(app_client) -> None:
    """GET /api/v1/agents/{id} should return 404 for unknown agent."""
    response = await app_client.get("/api/v1/agents/nonexistent-id-xyz")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_agent_metrics(app_client) -> None:
    """GET /api/v1/agents/{id}/metrics should return metrics for an agent."""
    await app_client.post(
        "/v1/traces",
        json=_make_span_payload(agent_name="metrics-agent", span_id="sp3"),
    )
    agents_resp = await app_client.get("/api/v1/agents")
    agents = agents_resp.json()["agents"]
    agent_id = next(a["id"] for a in agents if a["name"] == "metrics-agent")

    response = await app_client.get(f"/api/v1/agents/{agent_id}/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_tokens" in data
    assert "total_spans" in data


@pytest.mark.asyncio
async def test_metrics_summary(app_client) -> None:
    """GET /api/v1/metrics/summary should return aggregated metrics."""
    await app_client.post(
        "/v1/traces",
        json=_make_span_payload(agent_name="summary-agent", span_id="sp4"),
    )
    response = await app_client.get("/api/v1/metrics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_spans" in data
    assert "total_tokens" in data
    assert "total_cost_usd" in data
    assert "avg_latency_ms" in data
    assert "error_count" in data
