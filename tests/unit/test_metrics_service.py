"""Tests for metrics aggregation service — windowed rollups."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from argus.models.agent import Agent
from argus.models.metric_snapshot import MetricSnapshot
from argus.models.span import Span
from argus.models.trace import Trace


async def _create_agent_with_spans(
    session,
    agent_name: str = "metrics-agent",
    num_spans: int = 5,
    base_time: datetime | None = None,
) -> Agent:
    """Helper to create an agent with traces and spans for metrics tests."""
    if base_time is None:
        base_time = datetime.now(UTC)

    agent = Agent(name=agent_name, framework="test")
    session.add(agent)
    await session.flush()

    trace = Trace(
        id=f"trace-{agent_name}",
        agent_id=agent.id,
        status="completed",
        started_at=base_time,
        ended_at=base_time + timedelta(seconds=10),
    )
    session.add(trace)
    await session.flush()

    for i in range(num_spans):
        latency = 100 + i * 50  # 100, 150, 200, 250, 300
        span = Span(
            id=f"span-{agent_name}-{i}",
            trace_id=trace.id,
            operation_name="chat",
            model="gpt-4o",
            provider="openai",
            input_tokens=100 * (i + 1),
            output_tokens=50 * (i + 1),
            total_tokens=150 * (i + 1),
            latency_ms=latency,
            status="ok" if i < 4 else "error",
            started_at=base_time + timedelta(seconds=i),
            ended_at=base_time + timedelta(seconds=i, milliseconds=latency),
        )
        session.add(span)

    await session.commit()
    return agent


@pytest.mark.asyncio
async def test_aggregate_creates_snapshot(async_session) -> None:
    """Metrics aggregation should create a MetricSnapshot for the given window."""
    from argus.services.metrics import MetricsService

    agent = await _create_agent_with_spans(async_session, "agg-agent", num_spans=5)
    service = MetricsService()
    now = datetime.now(UTC)

    snapshot = await service.aggregate(
        session=async_session,
        agent_id=agent.id,
        window_size="1m",
        window_start=now - timedelta(minutes=5),
        window_end=now + timedelta(minutes=1),
    )

    assert snapshot is not None
    assert snapshot.agent_id == agent.id
    assert snapshot.window_size == "1m"
    assert snapshot.total_tokens > 0


@pytest.mark.asyncio
async def test_aggregate_token_counts(async_session) -> None:
    """Metrics aggregation should sum token counts correctly."""
    from argus.services.metrics import MetricsService

    agent = await _create_agent_with_spans(async_session, "token-agent", num_spans=3)
    service = MetricsService()
    now = datetime.now(UTC)

    snapshot = await service.aggregate(
        session=async_session,
        agent_id=agent.id,
        window_size="1h",
        window_start=now - timedelta(hours=1),
        window_end=now + timedelta(hours=1),
    )

    # input_tokens: 100 + 200 + 300 = 600
    # output_tokens: 50 + 100 + 150 = 300
    # total_tokens: 150 + 300 + 450 = 900
    assert snapshot.total_tokens == 900


@pytest.mark.asyncio
async def test_aggregate_latency_stats(async_session) -> None:
    """Metrics aggregation should compute avg, p95, p99 latency."""
    from argus.services.metrics import MetricsService

    agent = await _create_agent_with_spans(async_session, "latency-agent", num_spans=5)
    service = MetricsService()
    now = datetime.now(UTC)

    snapshot = await service.aggregate(
        session=async_session,
        agent_id=agent.id,
        window_size="1h",
        window_start=now - timedelta(hours=1),
        window_end=now + timedelta(hours=1),
    )

    # latencies: [100, 150, 200, 250, 300]
    assert snapshot.avg_latency_ms == pytest.approx(200.0, abs=1)
    assert snapshot.p95_latency_ms >= 250
    assert snapshot.p99_latency_ms >= 280


@pytest.mark.asyncio
async def test_aggregate_empty_window(async_session) -> None:
    """Metrics aggregation for an empty window should return zero-value snapshot."""
    from argus.services.metrics import MetricsService

    agent = Agent(name="empty-agent", framework="test")
    async_session.add(agent)
    await async_session.commit()

    service = MetricsService()
    far_past = datetime(2020, 1, 1, tzinfo=UTC)

    snapshot = await service.aggregate(
        session=async_session,
        agent_id=agent.id,
        window_size="1m",
        window_start=far_past,
        window_end=far_past + timedelta(minutes=1),
    )

    assert snapshot.total_tokens == 0
    assert snapshot.total_traces == 0
    assert snapshot.avg_latency_ms == 0.0


@pytest.mark.asyncio
async def test_aggregate_stores_snapshot(async_session) -> None:
    """Metrics aggregation should persist the snapshot to the database."""
    from argus.services.metrics import MetricsService

    agent = await _create_agent_with_spans(async_session, "persist-agent", num_spans=2)
    service = MetricsService()
    now = datetime.now(UTC)

    await service.aggregate(
        session=async_session,
        agent_id=agent.id,
        window_size="5m",
        window_start=now - timedelta(minutes=10),
        window_end=now + timedelta(minutes=1),
    )

    # Verify persisted
    result = await async_session.execute(
        select(MetricSnapshot).where(MetricSnapshot.agent_id == agent.id)
    )
    stored = result.scalars().all()
    assert len(stored) >= 1


@pytest.mark.asyncio
async def test_get_summary_returns_metrics(async_session) -> None:
    """get_summary should return aggregated metrics across all agents."""
    from argus.services.metrics import MetricsService

    await _create_agent_with_spans(async_session, "summary-agent-1", num_spans=3)
    await _create_agent_with_spans(async_session, "summary-agent-2", num_spans=2)

    service = MetricsService()
    now = datetime.now(UTC)

    summary = await service.get_summary(
        session=async_session,
        time_start=now - timedelta(hours=1),
        time_end=now + timedelta(hours=1),
    )

    assert summary["total_spans"] == 5
    assert summary["total_tokens"] > 0
    assert "avg_latency_ms" in summary
    assert "error_count" in summary
