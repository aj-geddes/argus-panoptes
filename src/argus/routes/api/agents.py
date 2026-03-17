"""Agent API routes — list, detail, metrics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from argus.core.database import get_session
from argus.services.agent_registry import AgentRegistry
from argus.services.metrics import MetricsService

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

_registry = AgentRegistry()
_metrics = MetricsService()


@router.get("")
async def list_agents(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List all registered agents."""
    agents = await _registry.list_agents(session)
    return {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "framework": a.framework,
                "description": a.description,
                "tags": a.tags,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
            }
            for a in agents
        ],
        "total": len(agents),
    }


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get agent details by ID."""
    agent = await _registry.get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "id": agent.id,
        "name": agent.name,
        "framework": agent.framework,
        "description": agent.description,
        "tags": agent.tags,
        "created_at": agent.created_at.isoformat(),
        "updated_at": agent.updated_at.isoformat(),
    }


@router.get("/{agent_id}/metrics")
async def get_agent_metrics(
    agent_id: str,
    time_range: str = "1h",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get metrics for a specific agent within a time range."""
    agent = await _registry.get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    now = datetime.now(UTC)
    delta = _parse_time_range(time_range)
    time_start = now - delta

    # Get spans-based summary for this agent
    from sqlmodel import func, select

    from argus.models.span import Span
    from argus.models.trace import Trace

    span_count_q = (
        select(func.count())
        .select_from(Span)
        .join(Trace, Span.trace_id == Trace.id)
        .where(Trace.agent_id == agent_id, Span.started_at >= time_start)
    )
    result = await session.execute(span_count_q)
    total_spans = result.scalar() or 0

    token_q = (
        select(func.coalesce(func.sum(Span.total_tokens), 0))
        .join(Trace, Span.trace_id == Trace.id)
        .where(Trace.agent_id == agent_id, Span.started_at >= time_start)
    )
    result = await session.execute(token_q)
    total_tokens = result.scalar() or 0

    cost_q = (
        select(func.coalesce(func.sum(Span.cost_usd), 0.0))
        .join(Trace, Span.trace_id == Trace.id)
        .where(Trace.agent_id == agent_id, Span.started_at >= time_start)
    )
    result = await session.execute(cost_q)
    total_cost = result.scalar() or 0.0

    latency_q = (
        select(func.coalesce(func.avg(Span.latency_ms), 0.0))
        .join(Trace, Span.trace_id == Trace.id)
        .where(
            Trace.agent_id == agent_id,
            Span.started_at >= time_start,
            Span.latency_ms > 0,
        )
    )
    result = await session.execute(latency_q)
    avg_latency = result.scalar() or 0.0

    return {
        "agent_id": agent_id,
        "time_range": time_range,
        "total_spans": total_spans,
        "total_tokens": int(total_tokens),
        "total_cost_usd": float(total_cost),
        "avg_latency_ms": float(avg_latency),
    }


def _parse_time_range(time_range: str) -> timedelta:
    """Parse a time range string like '1h', '24h', '7d' into a timedelta."""
    unit = time_range[-1]
    value = int(time_range[:-1])
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    return timedelta(hours=1)  # default fallback
