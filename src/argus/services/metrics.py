"""Metrics aggregation service — windowed rollups for dashboard."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from argus.models.metric_snapshot import MetricSnapshot
from argus.models.span import Span
from argus.models.trace import Trace

logger = logging.getLogger(__name__)


class MetricsService:
    """Aggregates span data into MetricSnapshot records for fast dashboard queries."""

    async def aggregate(
        self,
        session: AsyncSession,
        agent_id: str,
        window_size: str,
        window_start: datetime,
        window_end: datetime,
    ) -> MetricSnapshot:
        """Aggregate span data for a given agent and time window.

        Creates and persists a MetricSnapshot. Returns the snapshot.
        """
        # Query spans in the time window for this agent
        span_query = (
            select(Span)
            .join(Trace, Span.trace_id == Trace.id)
            .where(
                Trace.agent_id == agent_id,
                Span.started_at >= window_start,
                Span.started_at < window_end,
            )
        )
        result = await session.execute(span_query)
        spans = result.scalars().all()

        # Compute aggregates
        total_tokens = 0
        total_cost = 0.0
        latencies: list[int] = []
        error_count = 0

        for span in spans:
            total_tokens += span.total_tokens
            total_cost += span.cost_usd
            if span.latency_ms > 0:
                latencies.append(span.latency_ms)
            if span.status == "error":
                error_count += 1

        # Count traces in window
        trace_query = (
            select(func.count())
            .select_from(Trace)
            .where(
                Trace.agent_id == agent_id,
                Trace.started_at >= window_start,
                Trace.started_at < window_end,
            )
        )
        trace_result = await session.execute(trace_query)
        total_traces = trace_result.scalar() or 0

        # Latency percentiles
        avg_latency = 0.0
        p95_latency = 0.0
        p99_latency = 0.0
        if latencies:
            latencies.sort()
            avg_latency = sum(latencies) / len(latencies)
            p95_latency = _percentile(latencies, 95)
            p99_latency = _percentile(latencies, 99)

        # Count tool calls
        # Tool calls are tracked in the spans with operation_name containing "tool"
        # But for simplicity, we track via the ToolCall model
        from argus.models.tool_call import ToolCall

        tool_query = (
            select(func.count())
            .select_from(ToolCall)
            .join(Span, ToolCall.span_id == Span.id)
            .join(Trace, Span.trace_id == Trace.id)
            .where(
                Trace.agent_id == agent_id,
                ToolCall.called_at >= window_start,
                ToolCall.called_at < window_end,
            )
        )
        tool_result = await session.execute(tool_query)
        tool_calls_total = tool_result.scalar() or 0

        tool_failed_query = (
            select(func.count())
            .select_from(ToolCall)
            .join(Span, ToolCall.span_id == Span.id)
            .join(Trace, Span.trace_id == Trace.id)
            .where(
                Trace.agent_id == agent_id,
                ToolCall.called_at >= window_start,
                ToolCall.called_at < window_end,
                ToolCall.success == False,  # noqa: E712
            )
        )
        tool_failed_result = await session.execute(tool_failed_query)
        tool_calls_failed = tool_failed_result.scalar() or 0

        snapshot = MetricSnapshot(
            agent_id=agent_id,
            window_start=window_start,
            window_size=window_size,
            total_traces=total_traces,
            successful_traces=total_traces - error_count,
            failed_traces=error_count,
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            tool_calls_total=tool_calls_total,
            tool_calls_failed=tool_calls_failed,
        )

        session.add(snapshot)
        await session.flush()
        logger.info(
            "Aggregated metrics for agent %s, window %s: %d tokens, %d traces",
            agent_id,
            window_size,
            total_tokens,
            total_traces,
        )
        return snapshot

    async def get_summary(
        self,
        session: AsyncSession,
        time_start: datetime,
        time_end: datetime,
    ) -> dict[str, Any]:
        """Get an aggregated metrics summary across all agents for a time range."""
        # Total spans
        span_count_q = (
            select(func.count())
            .select_from(Span)
            .where(Span.started_at >= time_start, Span.started_at < time_end)
        )
        result = await session.execute(span_count_q)
        total_spans = result.scalar() or 0

        # Total tokens
        token_q = select(func.coalesce(func.sum(Span.total_tokens), 0)).where(
            Span.started_at >= time_start, Span.started_at < time_end
        )
        result = await session.execute(token_q)
        total_tokens = result.scalar() or 0

        # Total cost
        cost_q = select(func.coalesce(func.sum(Span.cost_usd), 0.0)).where(
            Span.started_at >= time_start, Span.started_at < time_end
        )
        result = await session.execute(cost_q)
        total_cost = result.scalar() or 0.0

        # Avg latency
        latency_q = select(func.coalesce(func.avg(Span.latency_ms), 0.0)).where(
            Span.started_at >= time_start,
            Span.started_at < time_end,
            Span.latency_ms > 0,
        )
        result = await session.execute(latency_q)
        avg_latency = result.scalar() or 0.0

        # Error count
        error_q = (
            select(func.count())
            .select_from(Span)
            .where(
                Span.started_at >= time_start,
                Span.started_at < time_end,
                Span.status == "error",
            )
        )
        result = await session.execute(error_q)
        error_count = result.scalar() or 0

        # Total traces
        trace_count_q = (
            select(func.count())
            .select_from(Trace)
            .where(Trace.started_at >= time_start, Trace.started_at < time_end)
        )
        result = await session.execute(trace_count_q)
        total_traces = result.scalar() or 0

        return {
            "total_spans": total_spans,
            "total_tokens": int(total_tokens),
            "total_cost_usd": float(total_cost),
            "avg_latency_ms": float(avg_latency),
            "error_count": error_count,
            "total_traces": total_traces,
        }


def _percentile(sorted_data: list[int], p: float) -> float:
    """Calculate the p-th percentile of a sorted list."""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    k = (p / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_data[int(k)])
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)
