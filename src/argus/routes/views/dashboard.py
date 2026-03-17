"""Dashboard view — renders the main overview page."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from argus.core.database import get_session
from argus.models.agent import Agent
from argus.models.span import Span
from argus.models.trace import Trace

router = APIRouter()

templates = Jinja2Templates(directory="src/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Render the main dashboard page."""
    # Get summary stats
    agent_count_result = await session.execute(select(func.count()).select_from(Agent))
    agent_count = agent_count_result.scalar() or 0

    trace_count_result = await session.execute(select(func.count()).select_from(Trace))
    trace_count = trace_count_result.scalar() or 0

    span_count_result = await session.execute(select(func.count()).select_from(Span))
    span_count = span_count_result.scalar() or 0

    # Get recent spans
    recent_spans_result = await session.execute(
        select(Span).order_by(Span.started_at.desc()).limit(20)  # type: ignore[attr-defined]
    )
    recent_spans = recent_spans_result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="pages/dashboard.html",
        context={
            "agent_count": agent_count,
            "trace_count": trace_count,
            "span_count": span_count,
            "recent_spans": recent_spans,
        },
    )
