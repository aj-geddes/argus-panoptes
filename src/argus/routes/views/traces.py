"""Trace view routes — HTML responses for trace explorer UI."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from argus.core.database import get_session
from argus.services.trace_query import TraceQueryService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory="src/templates")

_service = TraceQueryService()


@router.get("/traces", response_class=HTMLResponse)
async def traces_list(
    request: Request,
    search: str | None = None,
    status: str | None = None,
    agent_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Render the trace list page."""
    result = await _service.list_traces(
        session,
        search=search,
        status=status,
        agent_id=agent_id,
    )
    return templates.TemplateResponse(
        request=request,
        name="pages/traces.html",
        context={
            "traces": result["traces"],
            "total": result["total"],
            "search": search or "",
            "status_filter": status or "",
            "agent_id_filter": agent_id or "",
        },
    )


@router.get("/traces/search", response_class=HTMLResponse)
async def traces_search_partial(
    request: Request,
    q: str = "",
    status: str | None = None,
    agent_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Return the trace list partial (for HTMX search updates)."""
    result = await _service.list_traces(
        session,
        search=q if q else None,
        status=status,
        agent_id=agent_id,
    )
    return templates.TemplateResponse(
        request=request,
        name="components/trace_list.html",
        context={
            "traces": result["traces"],
            "total": result["total"],
        },
    )


@router.get("/traces/compare", response_class=HTMLResponse)
async def traces_compare(
    request: Request,
    trace_ids: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Render the trace comparison page."""
    traces: list[dict[str, Any]] = []
    if trace_ids:
        ids = [tid.strip() for tid in trace_ids.split(",") if tid.strip()]
        traces = await _service.compare_traces(session, ids)

    return templates.TemplateResponse(
        request=request,
        name="pages/trace_compare.html",
        context={
            "traces": traces,
            "trace_ids": trace_ids or "",
        },
    )


@router.get("/traces/spans/{span_id}/tool-calls", response_class=HTMLResponse)
async def tool_call_panel(
    request: Request,
    span_id: str,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Return the tool call inspection panel partial."""
    tool_calls = await _service.get_tool_calls_for_span(session, span_id)
    return templates.TemplateResponse(
        request=request,
        name="components/tool_call_panel.html",
        context={
            "tool_calls": tool_calls,
            "span_id": span_id,
        },
    )


@router.get("/traces/{trace_id}", response_class=HTMLResponse)
async def trace_detail(
    request: Request,
    trace_id: str,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Render the trace detail page with span tree."""
    result = await _service.get_trace_detail(session, trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    return templates.TemplateResponse(
        request=request,
        name="pages/trace_detail.html",
        context={
            "trace": result,
            "span_tree": result["span_tree"],
            "tool_calls": result["tool_calls"],
        },
    )
