"""Tests for the ingestion service (process_ingest_request and helpers)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlmodel import select

from argus.schemas.otlp import (
    Attribute,
    AttributeValue,
    IngestRequest,
    Resource,
    ResourceSpans,
    ScopeSpans,
    SpanData,
)


@pytest.mark.asyncio
async def test_get_or_create_agent_creates_new(async_session) -> None:
    """get_or_create_agent should create a new agent if one doesn't exist."""
    from argus.services.ingestion import get_or_create_agent

    agent = await get_or_create_agent(async_session, "new-agent", "langgraph")
    assert agent.name == "new-agent"
    assert agent.framework == "langgraph"
    assert agent.id is not None


@pytest.mark.asyncio
async def test_get_or_create_agent_returns_existing(async_session) -> None:
    """get_or_create_agent should return an existing agent by name."""
    from argus.services.ingestion import get_or_create_agent

    agent1 = await get_or_create_agent(async_session, "existing-agent", "crewai")
    await async_session.commit()
    agent2 = await get_or_create_agent(async_session, "existing-agent", "crewai")
    assert agent1.id == agent2.id


@pytest.mark.asyncio
async def test_get_or_create_trace_creates_new(async_session) -> None:
    """get_or_create_trace should create a new trace if one doesn't exist."""
    from argus.services.ingestion import get_or_create_agent, get_or_create_trace

    agent = await get_or_create_agent(async_session, "trace-agent")
    await async_session.flush()
    trace = await get_or_create_trace(async_session, "new-trace-id", agent.id, datetime.now(UTC))
    assert trace.id == "new-trace-id"
    assert trace.agent_id == agent.id


@pytest.mark.asyncio
async def test_get_or_create_trace_returns_existing(async_session) -> None:
    """get_or_create_trace should return an existing trace by ID."""
    from argus.services.ingestion import get_or_create_agent, get_or_create_trace

    agent = await get_or_create_agent(async_session, "trace-agent-2")
    await async_session.flush()
    now = datetime.now(UTC)
    trace1 = await get_or_create_trace(async_session, "existing-trace", agent.id, now)
    await async_session.commit()
    trace2 = await get_or_create_trace(async_session, "existing-trace", agent.id, now)
    assert trace1.id == trace2.id


@pytest.mark.asyncio
async def test_process_ingest_request_full(async_session) -> None:
    """process_ingest_request should store spans, agents, traces, and tool calls."""
    from argus.models.span import Span
    from argus.services.ingestion import process_ingest_request

    request = IngestRequest(
        resourceSpans=[
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        Attribute(
                            key="gen_ai.agent.name",
                            value=AttributeValue(stringValue="full-test-agent"),
                        )
                    ]
                ),
                scopeSpans=[
                    ScopeSpans(
                        spans=[
                            SpanData(
                                traceId="full-trace",
                                spanId="full-span",
                                name="chat gpt-4o",
                                attributes=[
                                    Attribute(
                                        key="gen_ai.operation.name",
                                        value=AttributeValue(stringValue="chat"),
                                    ),
                                    Attribute(
                                        key="gen_ai.request.model",
                                        value=AttributeValue(stringValue="gpt-4o"),
                                    ),
                                    Attribute(
                                        key="gen_ai.provider.name",
                                        value=AttributeValue(stringValue="openai"),
                                    ),
                                    Attribute(
                                        key="gen_ai.usage.input_tokens",
                                        value=AttributeValue(intValue=200),
                                    ),
                                    Attribute(
                                        key="gen_ai.usage.output_tokens",
                                        value=AttributeValue(intValue=100),
                                    ),
                                ],
                                startTimeUnixNano="1710000000000000000",
                                endTimeUnixNano="1710000001000000000",
                            )
                        ]
                    )
                ],
            )
        ]
    )

    count = await process_ingest_request(async_session, request)
    assert count == 1

    # Verify the span was stored correctly
    result = await async_session.execute(select(Span).where(Span.id == "full-span"))
    span = result.scalar_one()
    assert span.operation_name == "chat"
    assert span.model == "gpt-4o"
    assert span.provider == "openai"
    assert span.input_tokens == 200
    assert span.output_tokens == 100
    assert span.total_tokens == 300


@pytest.mark.asyncio
async def test_process_ingest_request_with_tool_call(async_session) -> None:
    """process_ingest_request should create ToolCall records for tool spans."""
    from argus.models.tool_call import ToolCall
    from argus.services.ingestion import process_ingest_request

    request = IngestRequest(
        resourceSpans=[
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        Attribute(
                            key="gen_ai.agent.name",
                            value=AttributeValue(stringValue="tool-agent"),
                        )
                    ]
                ),
                scopeSpans=[
                    ScopeSpans(
                        spans=[
                            SpanData(
                                traceId="tool-trace",
                                spanId="tool-span",
                                name="tool_call web_search",
                                attributes=[
                                    Attribute(
                                        key="gen_ai.operation.name",
                                        value=AttributeValue(stringValue="tool_call"),
                                    ),
                                    Attribute(
                                        key="gen_ai.tool.name",
                                        value=AttributeValue(stringValue="web_search"),
                                    ),
                                    Attribute(
                                        key="gen_ai.tool.type",
                                        value=AttributeValue(stringValue="function"),
                                    ),
                                ],
                                startTimeUnixNano="1710000000000000000",
                                endTimeUnixNano="1710000000500000000",
                            )
                        ]
                    )
                ],
            )
        ]
    )

    count = await process_ingest_request(async_session, request)
    assert count == 1

    # Verify tool call was stored
    result = await async_session.execute(select(ToolCall).where(ToolCall.tool_name == "web_search"))
    tool_call = result.scalar_one()
    assert tool_call.tool_type == "function"
    assert tool_call.success is True


@pytest.mark.asyncio
async def test_process_ingest_empty_request(async_session) -> None:
    """process_ingest_request with no spans should return 0."""
    from argus.services.ingestion import process_ingest_request

    request = IngestRequest(resourceSpans=[])
    count = await process_ingest_request(async_session, request)
    assert count == 0


def test_get_attr_helper() -> None:
    """_get_attr should extract values from attribute lists."""
    from argus.services.ingestion import _get_attr

    attrs = [
        Attribute(key="string_key", value=AttributeValue(stringValue="hello")),
        Attribute(key="int_key", value=AttributeValue(intValue=42)),
        Attribute(key="bool_key", value=AttributeValue(boolValue=True)),
        Attribute(key="double_key", value=AttributeValue(doubleValue=3.14)),
    ]
    assert _get_attr(attrs, "string_key") == "hello"
    assert _get_attr(attrs, "int_key") == 42
    assert _get_attr(attrs, "bool_key") is True
    assert _get_attr(attrs, "double_key") == 3.14
    assert _get_attr(attrs, "missing_key") is None


def test_nano_to_datetime() -> None:
    """_nano_to_datetime should convert nanosecond timestamps."""
    from argus.services.ingestion import _nano_to_datetime

    dt = _nano_to_datetime("1710000000000000000")
    assert dt.year == 2024
    assert dt.tzinfo is not None


def test_nano_to_datetime_invalid() -> None:
    """_nano_to_datetime should handle invalid values gracefully."""
    from argus.services.ingestion import _nano_to_datetime

    dt = _nano_to_datetime("not-a-number")
    assert dt.tzinfo is not None  # Should return current time
