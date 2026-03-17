"""Tests for SQLAlchemy / SQLModel data models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio
async def test_all_tables_created(async_engine) -> None:
    """All 5 core tables should be created in the database."""
    # Import models to ensure they register with SQLModel metadata

    async with async_engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
    assert "agent" in tables
    assert "trace" in tables
    assert "span" in tables
    assert "toolcall" in tables
    assert "metricsnapshot" in tables


@pytest.mark.asyncio
async def test_create_agent(async_session) -> None:
    """Should be able to create and persist an Agent."""
    from argus.models.agent import Agent

    agent = Agent(
        name="test-agent",
        framework="langgraph",
        description="A test agent",
    )
    async_session.add(agent)
    await async_session.commit()
    await async_session.refresh(agent)

    assert agent.id is not None
    assert agent.name == "test-agent"
    assert agent.framework == "langgraph"
    assert agent.created_at is not None


@pytest.mark.asyncio
async def test_create_trace(async_session) -> None:
    """Should be able to create a Trace linked to an Agent."""
    from argus.models.agent import Agent
    from argus.models.trace import Trace

    agent = Agent(name="trace-test-agent", framework="crewai")
    async_session.add(agent)
    await async_session.commit()
    await async_session.refresh(agent)

    trace = Trace(
        id="trace-001",
        agent_id=agent.id,
        status="running",
        started_at=datetime.now(UTC),
    )
    async_session.add(trace)
    await async_session.commit()
    await async_session.refresh(trace)

    assert trace.id == "trace-001"
    assert trace.agent_id == agent.id
    assert trace.status == "running"


@pytest.mark.asyncio
async def test_create_span(async_session) -> None:
    """Should be able to create a Span linked to a Trace."""
    from argus.models.agent import Agent
    from argus.models.span import Span
    from argus.models.trace import Trace

    agent = Agent(name="span-test-agent", framework="openai")
    async_session.add(agent)
    await async_session.commit()
    await async_session.refresh(agent)

    trace = Trace(
        id="trace-002",
        agent_id=agent.id,
        status="completed",
        started_at=datetime.now(UTC),
    )
    async_session.add(trace)
    await async_session.commit()

    span = Span(
        id="span-001",
        trace_id="trace-002",
        operation_name="chat",
        model="gpt-4o",
        provider="openai",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cost_usd=0.001,
        latency_ms=500,
        status="ok",
        started_at=datetime.now(UTC),
    )
    async_session.add(span)
    await async_session.commit()
    await async_session.refresh(span)

    assert span.id == "span-001"
    assert span.trace_id == "trace-002"
    assert span.input_tokens == 100
    assert span.output_tokens == 50
    assert span.total_tokens == 150


@pytest.mark.asyncio
async def test_create_tool_call(async_session) -> None:
    """Should be able to create a ToolCall linked to a Span."""
    from argus.models.agent import Agent
    from argus.models.span import Span
    from argus.models.tool_call import ToolCall
    from argus.models.trace import Trace

    agent = Agent(name="tool-test-agent", framework="custom")
    async_session.add(agent)
    await async_session.commit()
    await async_session.refresh(agent)

    trace = Trace(
        id="trace-003",
        agent_id=agent.id,
        status="completed",
        started_at=datetime.now(UTC),
    )
    async_session.add(trace)
    await async_session.commit()

    span = Span(
        id="span-002",
        trace_id="trace-003",
        operation_name="tool_call",
        started_at=datetime.now(UTC),
    )
    async_session.add(span)
    await async_session.commit()

    tool_call = ToolCall(
        span_id="span-002",
        tool_name="search",
        tool_type="function",
        input_data={"query": "test"},
        output_data={"result": "found"},
        success=True,
        duration_ms=120,
        called_at=datetime.now(UTC),
    )
    async_session.add(tool_call)
    await async_session.commit()
    await async_session.refresh(tool_call)

    assert tool_call.id is not None
    assert tool_call.span_id == "span-002"
    assert tool_call.tool_name == "search"
    assert tool_call.success is True


@pytest.mark.asyncio
async def test_create_metric_snapshot(async_session) -> None:
    """Should be able to create a MetricSnapshot."""
    from argus.models.agent import Agent
    from argus.models.metric_snapshot import MetricSnapshot

    agent = Agent(name="metric-test-agent", framework="adk")
    async_session.add(agent)
    await async_session.commit()
    await async_session.refresh(agent)

    snapshot = MetricSnapshot(
        agent_id=agent.id,
        window_start=datetime.now(UTC),
        window_size="1m",
        total_traces=10,
        successful_traces=9,
        failed_traces=1,
        total_tokens=5000,
        total_cost_usd=0.05,
        avg_latency_ms=200.0,
        p95_latency_ms=450.0,
        p99_latency_ms=900.0,
        tool_calls_total=15,
        tool_calls_failed=2,
    )
    async_session.add(snapshot)
    await async_session.commit()
    await async_session.refresh(snapshot)

    assert snapshot.id is not None
    assert snapshot.total_traces == 10
    assert snapshot.total_cost_usd == 0.05


@pytest.mark.asyncio
async def test_agent_default_values(async_session) -> None:
    """Agent should have sensible defaults for optional fields."""
    from argus.models.agent import Agent

    agent = Agent(name="defaults-agent", framework="custom")
    async_session.add(agent)
    await async_session.commit()
    await async_session.refresh(agent)

    assert agent.tags == {}
    assert agent.config == {}
    assert agent.description is None
