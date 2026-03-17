"""Agent detail view — per-agent metrics, traces, and cost breakdown."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from argus.core.database import get_session
from argus.core.utils import parse_time_range
from argus.models.agent import Agent
from argus.models.span import Span
from argus.models.trace import Trace

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory="src/templates")


@router.get("/agents", response_class=HTMLResponse)
async def agents_list(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Render the agents list page."""
    result = await session.execute(select(Agent).order_by(Agent.name))
    agents = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="pages/agents.html",
        context={"agents": agents},
    )


@router.get("/agents/{agent_id}/detail", response_class=HTMLResponse)
async def agent_detail(
    request: Request,
    agent_id: str,
    time_range: str = "1h",
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Render the agent detail page with per-agent metrics."""
    # Get agent
    result = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    now = datetime.now(UTC)
    delta = parse_time_range(time_range)
    time_start = now - delta

    # Get per-agent metrics
    # Total traces
    trace_q = select(func.count()).select_from(Trace).where(Trace.agent_id == agent_id, Trace.started_at >= time_start)
    trace_result = await session.execute(trace_q)
    total_traces = trace_result.scalar() or 0

    # Total spans
    span_q = (
        select(func.count())
        .select_from(Span)
        .join(Trace, Span.trace_id == Trace.id)  # type: ignore[arg-type]
        .where(Trace.agent_id == agent_id, Span.started_at >= time_start)
    )
    span_result = await session.execute(span_q)
    total_spans = span_result.scalar() or 0

    # Total tokens
    token_q = (
        select(func.coalesce(func.sum(Span.total_tokens), 0))
        .join(Trace, Span.trace_id == Trace.id)  # type: ignore[arg-type]
        .where(Trace.agent_id == agent_id, Span.started_at >= time_start)
    )
    token_result = await session.execute(token_q)
    total_tokens = token_result.scalar() or 0

    # Total cost
    cost_q = (
        select(func.coalesce(func.sum(Span.cost_usd), 0.0))
        .join(Trace, Span.trace_id == Trace.id)  # type: ignore[arg-type]
        .where(Trace.agent_id == agent_id, Span.started_at >= time_start)
    )
    cost_result = await session.execute(cost_q)
    total_cost = cost_result.scalar() or 0.0

    # Avg latency
    latency_q = (
        select(func.coalesce(func.avg(Span.latency_ms), 0.0))
        .join(Trace, Span.trace_id == Trace.id)  # type: ignore[arg-type]
        .where(Trace.agent_id == agent_id, Span.started_at >= time_start, Span.latency_ms > 0)
    )
    latency_result = await session.execute(latency_q)
    avg_latency = latency_result.scalar() or 0.0

    # Error count
    error_q = (
        select(func.count())
        .select_from(Span)
        .join(Trace, Span.trace_id == Trace.id)  # type: ignore[arg-type]
        .where(Trace.agent_id == agent_id, Span.started_at >= time_start, Span.status == "error")
    )
    error_result = await session.execute(error_q)
    error_count = error_result.scalar() or 0

    # Recent traces for this agent
    recent_traces_q = (
        select(Trace)
        .where(Trace.agent_id == agent_id)
        .order_by(Trace.started_at.desc())  # type: ignore[attr-defined]
        .limit(20)
    )
    recent_result = await session.execute(recent_traces_q)
    recent_traces = recent_result.scalars().all()

    # Recent spans for this agent
    recent_spans_q = (
        select(Span)
        .join(Trace, Span.trace_id == Trace.id)  # type: ignore[arg-type]
        .where(Trace.agent_id == agent_id)
        .order_by(Span.started_at.desc())  # type: ignore[attr-defined]
        .limit(20)
    )
    recent_spans_result = await session.execute(recent_spans_q)
    recent_spans = recent_spans_result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="pages/agent_detail.html",
        context={
            "agent": agent,
            "time_range": time_range,
            "total_traces": total_traces,
            "total_spans": total_spans,
            "total_tokens": int(total_tokens),
            "total_cost": float(total_cost),
            "avg_latency": float(avg_latency),
            "error_count": error_count,
            "recent_traces": recent_traces,
            "recent_spans": recent_spans,
        },
    )
