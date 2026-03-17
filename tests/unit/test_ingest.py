"""Tests for the REST ingestion endpoint."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_ingest_span_returns_200(app_client) -> None:
    """POST /v1/traces should accept a simplified span payload."""
    payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "gen_ai.agent.name",
                            "value": {"stringValue": "test-agent"},
                        }
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "abc123",
                                "spanId": "span-001",
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
                                        "key": "gen_ai.provider.name",
                                        "value": {"stringValue": "openai"},
                                    },
                                    {
                                        "key": "gen_ai.usage.input_tokens",
                                        "value": {"intValue": 100},
                                    },
                                    {
                                        "key": "gen_ai.usage.output_tokens",
                                        "value": {"intValue": 50},
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
    response = await app_client.post("/v1/traces", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["spans_accepted"] >= 1


@pytest.mark.asyncio
async def test_ingest_empty_payload_returns_200(app_client) -> None:
    """POST /v1/traces with empty resourceSpans should return 200 with 0 spans."""
    payload = {"resourceSpans": []}
    response = await app_client.post("/v1/traces", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["spans_accepted"] == 0


@pytest.mark.asyncio
async def test_ingest_invalid_payload_returns_422(app_client) -> None:
    """POST /v1/traces with invalid payload should return 422."""
    response = await app_client.post("/v1/traces", json={"invalid": "data"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_multiple_spans(app_client) -> None:
    """POST /v1/traces should accept multiple spans in a single request."""
    payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "gen_ai.agent.name",
                            "value": {"stringValue": "multi-agent"},
                        }
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "trace-multi",
                                "spanId": f"span-{i}",
                                "name": f"operation-{i}",
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
                            for i in range(3)
                        ]
                    }
                ],
            }
        ]
    }
    response = await app_client.post("/v1/traces", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["spans_accepted"] == 3


@pytest.mark.asyncio
async def test_ingest_span_with_tool_call(app_client) -> None:
    """POST /v1/traces should handle spans that include tool call attributes."""
    payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "gen_ai.agent.name",
                            "value": {"stringValue": "tool-agent"},
                        }
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "trace-tool",
                                "spanId": "span-tool-001",
                                "name": "tool_call search",
                                "attributes": [
                                    {
                                        "key": "gen_ai.operation.name",
                                        "value": {"stringValue": "tool_call"},
                                    },
                                    {
                                        "key": "gen_ai.tool.name",
                                        "value": {"stringValue": "web_search"},
                                    },
                                    {
                                        "key": "gen_ai.tool.type",
                                        "value": {"stringValue": "function"},
                                    },
                                ],
                                "startTimeUnixNano": "1710000000000000000",
                                "endTimeUnixNano": "1710000000500000000",
                            }
                        ]
                    }
                ],
            }
        ]
    }
    response = await app_client.post("/v1/traces", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["spans_accepted"] == 1
