"""Tests for enhanced OTLP ingestion — full GenAI semantic conventions v1.37."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from argus.models.agent import Agent
from argus.models.span import Span
from argus.models.tool_call import ToolCall
from argus.models.trace import Trace
from argus.schemas.otlp import IngestRequest
from argus.services.ingestion import process_ingest_request


def _make_otlp_payload(
    agent_name: str = "test-agent",
    trace_id: str = "abc123",
    span_id: str = "span-001",
    parent_span_id: str | None = None,
    operation_name: str = "chat",
    model: str = "gpt-4o",
    provider: str = "openai",
    input_tokens: int = 100,
    output_tokens: int = 50,
    conversation_id: str | None = None,
    tool_name: str | None = None,
    tool_type: str | None = None,
    error_type: str | None = None,
    extra_attributes: list | None = None,
) -> dict:
    """Build an OTLP payload dict with GenAI semantic conventions."""
    attributes = [
        {"key": "gen_ai.operation.name", "value": {"stringValue": operation_name}},
        {"key": "gen_ai.request.model", "value": {"stringValue": model}},
        {"key": "gen_ai.provider.name", "value": {"stringValue": provider}},
        {"key": "gen_ai.usage.input_tokens", "value": {"intValue": input_tokens}},
        {"key": "gen_ai.usage.output_tokens", "value": {"intValue": output_tokens}},
    ]

    if conversation_id:
        attributes.append({"key": "gen_ai.conversation.id", "value": {"stringValue": conversation_id}})
    if tool_name:
        attributes.append({"key": "gen_ai.tool.name", "value": {"stringValue": tool_name}})
    if tool_type:
        attributes.append({"key": "gen_ai.tool.type", "value": {"stringValue": tool_type}})
    if error_type:
        attributes.append({"key": "error.type", "value": {"stringValue": error_type}})
    if extra_attributes:
        attributes.extend(extra_attributes)

    now_ns = str(int(datetime.now(UTC).timestamp() * 1e9))
    start_ns = str(int((datetime.now(UTC).timestamp() - 1.5) * 1e9))

    span_data = {
        "traceId": trace_id,
        "spanId": span_id,
        "name": f"{operation_name} {model}",
        "attributes": attributes,
        "startTimeUnixNano": start_ns,
        "endTimeUnixNano": now_ns,
    }
    if parent_span_id:
        span_data["parentSpanId"] = parent_span_id

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "gen_ai.agent.name", "value": {"stringValue": agent_name}},
                    ]
                },
                "scopeSpans": [{"spans": [span_data]}],
            }
        ]
    }


class TestEnhancedOTLPIngestion:
    """Tests for full OTLP/JSON ingestion with GenAI v1.37 conventions."""

    async def test_basic_span_ingestion(self, async_session: AsyncSession) -> None:
        payload = _make_otlp_payload()
        request = IngestRequest(**payload)
        count = await process_ingest_request(async_session, request)
        assert count == 1

        # Verify span stored
        result = await async_session.execute(select(Span).where(Span.id == "span-001"))
        span = result.scalar_one()
        assert span.operation_name == "chat"
        assert span.model == "gpt-4o"
        assert span.provider == "openai"
        assert span.input_tokens == 100
        assert span.output_tokens == 50

    async def test_conversation_id_maps_to_session_id(self, async_session: AsyncSession) -> None:
        payload = _make_otlp_payload(
            trace_id="conv-trace",
            span_id="conv-span",
            conversation_id="conv-session-42",
        )
        request = IngestRequest(**payload)
        await process_ingest_request(async_session, request)

        result = await async_session.execute(select(Trace).where(Trace.id == "conv-trace"))
        trace = result.scalar_one()
        assert trace.session_id == "conv-session-42"

    async def test_error_type_mapped(self, async_session: AsyncSession) -> None:
        payload = _make_otlp_payload(
            trace_id="err-trace",
            span_id="err-span",
            error_type="TimeoutError",
        )
        request = IngestRequest(**payload)
        await process_ingest_request(async_session, request)

        result = await async_session.execute(select(Span).where(Span.id == "err-span"))
        span = result.scalar_one()
        assert span.status == "error"
        assert span.error_type == "TimeoutError"

    async def test_tool_call_ingestion(self, async_session: AsyncSession) -> None:
        payload = _make_otlp_payload(
            trace_id="tool-trace",
            span_id="tool-span",
            tool_name="web_search",
            tool_type="function",
        )
        request = IngestRequest(**payload)
        await process_ingest_request(async_session, request)

        result = await async_session.execute(select(ToolCall).where(ToolCall.span_id == "tool-span"))
        tc = result.scalar_one()
        assert tc.tool_name == "web_search"
        assert tc.tool_type == "function"

    async def test_parent_span_relationship(self, async_session: AsyncSession) -> None:
        # Ingest parent span first
        parent_payload = _make_otlp_payload(
            trace_id="parent-trace",
            span_id="parent-span",
        )
        request = IngestRequest(**parent_payload)
        await process_ingest_request(async_session, request)

        # Ingest child span
        child_payload = _make_otlp_payload(
            trace_id="parent-trace",
            span_id="child-span",
            parent_span_id="parent-span",
        )
        request = IngestRequest(**child_payload)
        await process_ingest_request(async_session, request)

        result = await async_session.execute(select(Span).where(Span.id == "child-span"))
        child = result.scalar_one()
        assert child.parent_span_id == "parent-span"

    async def test_agent_auto_registration(self, async_session: AsyncSession) -> None:
        payload = _make_otlp_payload(
            agent_name="brand-new-agent",
            trace_id="auto-trace",
            span_id="auto-span",
        )
        request = IngestRequest(**payload)
        await process_ingest_request(async_session, request)

        result = await async_session.execute(select(Agent).where(Agent.name == "brand-new-agent"))
        agent = result.scalar_one()
        assert agent.framework == "custom"

    async def test_multiple_spans_in_one_request(self, async_session: AsyncSession) -> None:
        now_ns = str(int(datetime.now(UTC).timestamp() * 1e9))
        start_ns = str(int((datetime.now(UTC).timestamp() - 1.0) * 1e9))

        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "gen_ai.agent.name", "value": {"stringValue": "multi-agent"}},
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "multi-trace",
                                    "spanId": "ms-1",
                                    "name": "chat gpt-4o",
                                    "attributes": [
                                        {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                                        {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                                        {"key": "gen_ai.provider.name", "value": {"stringValue": "openai"}},
                                        {"key": "gen_ai.usage.input_tokens", "value": {"intValue": 100}},
                                        {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 50}},
                                    ],
                                    "startTimeUnixNano": start_ns,
                                    "endTimeUnixNano": now_ns,
                                },
                                {
                                    "traceId": "multi-trace",
                                    "spanId": "ms-2",
                                    "parentSpanId": "ms-1",
                                    "name": "tool_call web_search",
                                    "attributes": [
                                        {"key": "gen_ai.operation.name", "value": {"stringValue": "tool_call"}},
                                        {"key": "gen_ai.tool.name", "value": {"stringValue": "web_search"}},
                                        {"key": "gen_ai.tool.type", "value": {"stringValue": "function"}},
                                    ],
                                    "startTimeUnixNano": start_ns,
                                    "endTimeUnixNano": now_ns,
                                },
                            ]
                        }
                    ],
                }
            ]
        }
        request = IngestRequest(**payload)
        count = await process_ingest_request(async_session, request)
        assert count == 2

    async def test_otlp_status_code_error(self, async_session: AsyncSession) -> None:
        """Test that OTLP status code maps correctly."""
        payload = _make_otlp_payload(
            trace_id="status-trace",
            span_id="status-span",
        )
        # Add status object to span
        payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["status"] = {
            "code": "STATUS_CODE_ERROR",
            "message": "something failed",
        }
        request = IngestRequest(**payload)
        await process_ingest_request(async_session, request)

        result = await async_session.execute(select(Span).where(Span.id == "status-span"))
        span = result.scalar_one()
        assert span.status == "error"

    async def test_framework_detection_from_scope(self, async_session: AsyncSession) -> None:
        """Test that scope name can hint at framework."""
        now_ns = str(int(datetime.now(UTC).timestamp() * 1e9))
        start_ns = str(int((datetime.now(UTC).timestamp() - 1.0) * 1e9))

        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "gen_ai.agent.name", "value": {"stringValue": "fw-agent"}},
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "langgraph"},
                            "spans": [
                                {
                                    "traceId": "fw-trace",
                                    "spanId": "fw-span",
                                    "name": "chat",
                                    "attributes": [
                                        {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                                    ],
                                    "startTimeUnixNano": start_ns,
                                    "endTimeUnixNano": now_ns,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        request = IngestRequest(**payload)
        await process_ingest_request(async_session, request)

        result = await async_session.execute(select(Agent).where(Agent.name == "fw-agent"))
        agent = result.scalar_one()
        assert agent.framework == "langgraph"
