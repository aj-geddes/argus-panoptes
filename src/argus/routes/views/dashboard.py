"""Dashboard view — renders the main overview page with metrics."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from argus.core.database import get_session
from argus.core.utils import parse_time_range
from argus.models.agent import Agent
from argus.models.span import Span
from argus.models.trace import Trace

router = APIRouter()

templates = Jinja2Templates(directory="src/templates")


async def _get_chart_data(
    session: AsyncSession,
    time_start: datetime,
    time_end: datetime,
) -> dict[str, Any]:
    """Build chart data for the dashboard."""
    # Get spans in time range for charts
    span_query = (
        select(Span).where(Span.started_at >= time_start, Span.started_at < time_end).order_by(Span.started_at)  # type: ignore[arg-type]
    )
    result = await session.execute(span_query)
    spans = result.scalars().all()

    # Token usage by model
    model_input: dict[str, int] = defaultdict(int)
    model_output: dict[str, int] = defaultdict(int)
    # Cost by model
    model_cost: dict[str, float] = defaultdict(float)
    # Latency data points
    latency_labels: list[str] = []
    latency_values: list[float] = []

    for span in spans:
        model_name = span.model or "unknown"
        model_input[model_name] += span.input_tokens
        model_output[model_name] += span.output_tokens
        model_cost[model_name] += span.cost_usd
        if span.latency_ms > 0:
            latency_labels.append(span.started_at.strftime("%H:%M:%S") if span.started_at else "")
            latency_values.append(float(span.latency_ms))

    # Build chart structures
    token_labels = list(model_input.keys())
    return {
        "token_labels": token_labels,
        "input_tokens": [model_input[m] for m in token_labels],
        "output_tokens": [model_output[m] for m in token_labels],
        "cost_labels": list(model_cost.keys()),
        "cost_values": [round(v, 6) for v in model_cost.values()],
        "latency_labels": latency_labels[-50:],  # Last 50 data points
        "latency_values": latency_values[-50:],
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    time_range: str = "1h",
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Render the main dashboard page."""
    now = datetime.now(UTC)
    delta = parse_time_range(time_range)
    time_start = now - delta

    # Get summary stats
    agent_count_result = await session.execute(select(func.count()).select_from(Agent))
    agent_count = agent_count_result.scalar() or 0

    trace_count_result = await session.execute(
        select(func.count()).select_from(Trace).where(Trace.started_at >= time_start)
    )
    trace_count = trace_count_result.scalar() or 0

    # Token count
    token_result = await session.execute(
        select(func.coalesce(func.sum(Span.total_tokens), 0)).where(Span.started_at >= time_start)
    )
    total_tokens = token_result.scalar() or 0

    # Total cost
    cost_result = await session.execute(
        select(func.coalesce(func.sum(Span.cost_usd), 0.0)).where(Span.started_at >= time_start)
    )
    total_cost = cost_result.scalar() or 0.0

    # Avg latency
    latency_result = await session.execute(
        select(func.coalesce(func.avg(Span.latency_ms), 0.0)).where(Span.started_at >= time_start, Span.latency_ms > 0)
    )
    avg_latency = latency_result.scalar() or 0.0

    # Error count
    error_result = await session.execute(
        select(func.count()).select_from(Span).where(Span.started_at >= time_start, Span.status == "error")
    )
    error_count = error_result.scalar() or 0

    # Get recent spans
    recent_spans_result = await session.execute(
        select(Span).order_by(Span.started_at.desc()).limit(20)  # type: ignore[attr-defined]
    )
    recent_spans = recent_spans_result.scalars().all()

    # Chart data
    chart_data = await _get_chart_data(session, time_start, now)

    return templates.TemplateResponse(
        request=request,
        name="pages/dashboard.html",
        context={
            "agent_count": agent_count,
            "trace_count": trace_count,
            "total_traces": trace_count,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "avg_latency": avg_latency,
            "error_count": error_count,
            "recent_spans": recent_spans,
            "chart_data": chart_data,
            "default_range": time_range,
        },
    )


@router.get("/partials/metrics-cards", response_class=HTMLResponse)
async def metrics_cards_partial(
    request: Request,
    time_range: str = "1h",
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Return the metrics cards partial (for HTMX re-render on time range change)."""
    now = datetime.now(UTC)
    delta = parse_time_range(time_range)
    time_start = now - delta

    agent_count_result = await session.execute(select(func.count()).select_from(Agent))
    agent_count = agent_count_result.scalar() or 0

    trace_count_result = await session.execute(
        select(func.count()).select_from(Trace).where(Trace.started_at >= time_start)
    )
    total_traces = trace_count_result.scalar() or 0

    token_result = await session.execute(
        select(func.coalesce(func.sum(Span.total_tokens), 0)).where(Span.started_at >= time_start)
    )
    total_tokens = token_result.scalar() or 0

    cost_result = await session.execute(
        select(func.coalesce(func.sum(Span.cost_usd), 0.0)).where(Span.started_at >= time_start)
    )
    total_cost = cost_result.scalar() or 0.0

    latency_result = await session.execute(
        select(func.coalesce(func.avg(Span.latency_ms), 0.0)).where(Span.started_at >= time_start, Span.latency_ms > 0)
    )
    avg_latency = latency_result.scalar() or 0.0

    error_result = await session.execute(
        select(func.count()).select_from(Span).where(Span.started_at >= time_start, Span.status == "error")
    )
    error_count = error_result.scalar() or 0

    return templates.TemplateResponse(
        request=request,
        name="components/metrics_cards.html",
        context={
            "agent_count": agent_count,
            "total_traces": total_traces,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "avg_latency": avg_latency,
            "error_count": error_count,
        },
    )
