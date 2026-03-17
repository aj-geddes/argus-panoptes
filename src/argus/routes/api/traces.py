"""Trace API routes — list, detail, compare (JSON responses)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from argus.core.database import get_session
from argus.services.trace_query import TraceQueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/traces", tags=["traces"])

_service = TraceQueryService()


@router.get("/compare")
async def compare_traces(
    trace_ids: str | None = Query(default=None, description="Comma-separated trace IDs"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Compare multiple traces side-by-side."""
    if not trace_ids:
        raise HTTPException(status_code=400, detail="trace_ids query parameter is required")

    ids = [tid.strip() for tid in trace_ids.split(",") if tid.strip()]
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="Too many trace IDs. Maximum is 10.")
    results = await _service.compare_traces(session, ids)
    return {"traces": results}


@router.get("/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get full trace detail with spans, span tree, and tool calls."""
    result = await _service.get_trace_detail(session, trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    # Convert span_tree to serializable format
    def _serialize_tree(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        serialized = []
        for node in nodes:
            span = node["span"]
            serialized.append(
                {
                    "span": {
                        "id": span.id,
                        "operation_name": span.operation_name,
                        "model": span.model,
                        "provider": span.provider,
                        "input_tokens": span.input_tokens,
                        "output_tokens": span.output_tokens,
                        "total_tokens": span.total_tokens,
                        "cost_usd": span.cost_usd,
                        "latency_ms": span.latency_ms,
                        "status": span.status,
                        "error_type": span.error_type,
                    },
                    "children": _serialize_tree(node["children"]),
                    "depth": node["depth"],
                }
            )
        return serialized

    result["span_tree"] = _serialize_tree(result["span_tree"])
    return result


@router.get("")
async def list_traces(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
    agent_id: str | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List traces with search, filtering, and pagination."""
    return await _service.list_traces(
        session,
        limit=limit,
        offset=offset,
        status=status,
        agent_id=agent_id,
        search=search,
    )
