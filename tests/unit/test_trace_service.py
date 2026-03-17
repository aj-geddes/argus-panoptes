"""Tests for the trace query service — search, filter, span tree building."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from argus.models.agent import Agent
from argus.models.span import Span
from argus.models.tool_call import ToolCall
from argus.models.trace import Trace
from argus.services.trace_query import TraceQueryService, build_span_tree


@pytest.fixture()
async def seeded_session(async_session: AsyncSession) -> AsyncSession:
    """Seed the database with agents, traces, spans, and tool calls."""
    now = datetime.now(UTC)

    # Create agents
    agent1 = Agent(id="agent-1", name="research-bot", framework="langgraph")
    agent2 = Agent(id="agent-2", name="code-assistant", framework="openai")
    async_session.add_all([agent1, agent2])
    await async_session.flush()

    # Create traces
    trace1 = Trace(
        id="trace-aaa",
        agent_id="agent-1",
        session_id="session-1",
        status="completed",
        started_at=now - timedelta(minutes=10),
        ended_at=now - timedelta(minutes=5),
        duration_ms=300000,
    )
    trace2 = Trace(
        id="trace-bbb",
        agent_id="agent-1",
        session_id="session-2",
        status="failed",
        started_at=now - timedelta(minutes=20),
        ended_at=now - timedelta(minutes=15),
        duration_ms=300000,
    )
    trace3 = Trace(
        id="trace-ccc",
        agent_id="agent-2",
        session_id=None,
        status="completed",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1, minutes=55),
        duration_ms=300000,
    )
    async_session.add_all([trace1, trace2, trace3])
    await async_session.flush()

    # Create spans for trace1 (parent + children)
    root_span = Span(
        id="span-root-1",
        trace_id="trace-aaa",
        parent_span_id=None,
        operation_name="invoke_agent",
        model="gpt-4o",
        provider="openai",
        input_tokens=500,
        output_tokens=200,
        total_tokens=700,
        cost_usd=0.003,
        latency_ms=1500,
        status="ok",
        started_at=now - timedelta(minutes=10),
        ended_at=now - timedelta(minutes=9),
    )
    child_span1 = Span(
        id="span-child-1",
        trace_id="trace-aaa",
        parent_span_id="span-root-1",
        operation_name="chat",
        model="gpt-4o",
        provider="openai",
        input_tokens=300,
        output_tokens=100,
        total_tokens=400,
        cost_usd=0.002,
        latency_ms=800,
        status="ok",
        started_at=now - timedelta(minutes=9, seconds=30),
        ended_at=now - timedelta(minutes=9),
    )
    child_span2 = Span(
        id="span-child-2",
        trace_id="trace-aaa",
        parent_span_id="span-root-1",
        operation_name="tool_call",
        model=None,
        provider=None,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        cost_usd=0.0,
        latency_ms=200,
        status="ok",
        started_at=now - timedelta(minutes=8, seconds=30),
        ended_at=now - timedelta(minutes=8),
    )
    grandchild_span = Span(
        id="span-grandchild-1",
        trace_id="trace-aaa",
        parent_span_id="span-child-1",
        operation_name="chat",
        model="gpt-4o",
        provider="openai",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cost_usd=0.001,
        latency_ms=300,
        status="ok",
        started_at=now - timedelta(minutes=9, seconds=20),
        ended_at=now - timedelta(minutes=9, seconds=10),
    )
    # Span for trace2
    error_span = Span(
        id="span-error-1",
        trace_id="trace-bbb",
        parent_span_id=None,
        operation_name="invoke_agent",
        model="claude-sonnet-4",
        provider="anthropic",
        input_tokens=1000,
        output_tokens=0,
        total_tokens=1000,
        cost_usd=0.003,
        latency_ms=5000,
        status="error",
        error_type="TimeoutError",
        started_at=now - timedelta(minutes=20),
        ended_at=now - timedelta(minutes=15),
    )
    # Span for trace3
    span_trace3 = Span(
        id="span-t3-1",
        trace_id="trace-ccc",
        parent_span_id=None,
        operation_name="chat",
        model="gpt-4o",
        provider="openai",
        input_tokens=200,
        output_tokens=100,
        total_tokens=300,
        cost_usd=0.002,
        latency_ms=600,
        status="ok",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1, minutes=55),
    )
    async_session.add_all([root_span, child_span1, child_span2, grandchild_span, error_span, span_trace3])
    await async_session.flush()

    # Create a tool call for span-child-2
    tool_call = ToolCall(
        span_id="span-child-2",
        tool_name="web_search",
        tool_type="function",
        input_data={"query": "test query"},
        output_data={"results": ["result1"]},
        success=True,
        duration_ms=200,
        called_at=now - timedelta(minutes=8, seconds=30),
    )
    async_session.add(tool_call)
    await async_session.commit()

    return async_session


class TestBuildSpanTree:
    """Tests for the span tree builder."""

    def test_empty_spans_returns_empty_list(self) -> None:
        tree = build_span_tree([])
        assert tree == []

    def test_single_root_span(self) -> None:
        now = datetime.now(UTC)
        span = Span(
            id="s1",
            trace_id="t1",
            parent_span_id=None,
            operation_name="chat",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            latency_ms=100,
            started_at=now,
        )
        tree = build_span_tree([span])
        assert len(tree) == 1
        assert tree[0]["span"].id == "s1"
        assert tree[0]["children"] == []
        assert tree[0]["depth"] == 0

    def test_parent_child_hierarchy(self) -> None:
        now = datetime.now(UTC)
        parent = Span(
            id="p1",
            trace_id="t1",
            parent_span_id=None,
            operation_name="invoke_agent",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            latency_ms=100,
            started_at=now,
        )
        child = Span(
            id="c1",
            trace_id="t1",
            parent_span_id="p1",
            operation_name="chat",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            latency_ms=50,
            started_at=now,
        )
        tree = build_span_tree([parent, child])
        assert len(tree) == 1
        root = tree[0]
        assert root["span"].id == "p1"
        assert root["depth"] == 0
        assert len(root["children"]) == 1
        assert root["children"][0]["span"].id == "c1"
        assert root["children"][0]["depth"] == 1

    def test_three_level_depth(self) -> None:
        now = datetime.now(UTC)
        spans = [
            Span(
                id="r",
                trace_id="t",
                parent_span_id=None,
                operation_name="root",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                latency_ms=0,
                started_at=now,
            ),
            Span(
                id="c",
                trace_id="t",
                parent_span_id="r",
                operation_name="child",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                latency_ms=0,
                started_at=now,
            ),
            Span(
                id="g",
                trace_id="t",
                parent_span_id="c",
                operation_name="grandchild",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                latency_ms=0,
                started_at=now,
            ),
        ]
        tree = build_span_tree(spans)
        assert len(tree) == 1
        assert tree[0]["children"][0]["children"][0]["span"].id == "g"
        assert tree[0]["children"][0]["children"][0]["depth"] == 2

    def test_multiple_roots(self) -> None:
        now = datetime.now(UTC)
        spans = [
            Span(
                id="r1",
                trace_id="t",
                parent_span_id=None,
                operation_name="root1",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                latency_ms=0,
                started_at=now,
            ),
            Span(
                id="r2",
                trace_id="t",
                parent_span_id=None,
                operation_name="root2",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                latency_ms=0,
                started_at=now,
            ),
        ]
        tree = build_span_tree(spans)
        assert len(tree) == 2


class TestTraceQueryService:
    """Tests for the trace query service."""

    @pytest.fixture()
    def service(self) -> TraceQueryService:
        return TraceQueryService()

    async def test_list_traces_returns_all(self, service: TraceQueryService, seeded_session: AsyncSession) -> None:
        result = await service.list_traces(seeded_session)
        assert result["total"] == 3
        assert len(result["traces"]) == 3

    async def test_list_traces_pagination_limit(self, service: TraceQueryService, seeded_session: AsyncSession) -> None:
        result = await service.list_traces(seeded_session, limit=2)
        assert len(result["traces"]) == 2
        assert result["total"] == 3

    async def test_list_traces_pagination_offset(
        self, service: TraceQueryService, seeded_session: AsyncSession
    ) -> None:
        result = await service.list_traces(seeded_session, limit=2, offset=2)
        assert len(result["traces"]) == 1
        assert result["total"] == 3

    async def test_list_traces_filter_by_status(self, service: TraceQueryService, seeded_session: AsyncSession) -> None:
        result = await service.list_traces(seeded_session, status="failed")
        assert result["total"] == 1
        assert result["traces"][0]["id"] == "trace-bbb"

    async def test_list_traces_filter_by_agent_id(
        self, service: TraceQueryService, seeded_session: AsyncSession
    ) -> None:
        result = await service.list_traces(seeded_session, agent_id="agent-2")
        assert result["total"] == 1
        assert result["traces"][0]["id"] == "trace-ccc"

    async def test_list_traces_search_by_agent_name(
        self, service: TraceQueryService, seeded_session: AsyncSession
    ) -> None:
        result = await service.list_traces(seeded_session, search="research")
        assert result["total"] == 2  # both traces from research-bot agent

    async def test_list_traces_search_by_trace_id(
        self, service: TraceQueryService, seeded_session: AsyncSession
    ) -> None:
        result = await service.list_traces(seeded_session, search="trace-ccc")
        assert result["total"] == 1

    async def test_list_traces_ordered_by_started_at_desc(
        self, service: TraceQueryService, seeded_session: AsyncSession
    ) -> None:
        result = await service.list_traces(seeded_session)
        times = [t["started_at"] for t in result["traces"]]
        # Most recent first
        assert times == sorted(times, reverse=True)

    async def test_get_trace_detail(self, service: TraceQueryService, seeded_session: AsyncSession) -> None:
        result = await service.get_trace_detail(seeded_session, "trace-aaa")
        assert result is not None
        assert result["id"] == "trace-aaa"
        assert len(result["spans"]) == 4  # root + 2 children + 1 grandchild
        assert result["span_tree"] is not None

    async def test_get_trace_detail_not_found(self, service: TraceQueryService, seeded_session: AsyncSession) -> None:
        result = await service.get_trace_detail(seeded_session, "nonexistent")
        assert result is None

    async def test_get_trace_detail_includes_tool_calls(
        self, service: TraceQueryService, seeded_session: AsyncSession
    ) -> None:
        result = await service.get_trace_detail(seeded_session, "trace-aaa")
        assert result is not None
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool_name"] == "web_search"

    async def test_get_tool_calls_for_span(self, service: TraceQueryService, seeded_session: AsyncSession) -> None:
        result = await service.get_tool_calls_for_span(seeded_session, "span-child-2")
        assert len(result) == 1
        assert result[0].tool_name == "web_search"

    async def test_compare_traces(self, service: TraceQueryService, seeded_session: AsyncSession) -> None:
        result = await service.compare_traces(seeded_session, ["trace-aaa", "trace-bbb"])
        assert len(result) == 2
        assert result[0]["id"] in ("trace-aaa", "trace-bbb")
        assert result[1]["id"] in ("trace-aaa", "trace-bbb")
        # Each entry should have span_tree
        for entry in result:
            assert "span_tree" in entry

    async def test_compare_traces_partial_not_found(
        self, service: TraceQueryService, seeded_session: AsyncSession
    ) -> None:
        result = await service.compare_traces(seeded_session, ["trace-aaa", "nonexistent"])
        assert len(result) == 1
