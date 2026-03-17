"""Trace query service — search, filter, span tree building."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from argus.models.agent import Agent
from argus.models.span import Span
from argus.models.tool_call import ToolCall
from argus.models.trace import Trace

logger = logging.getLogger(__name__)


def build_span_tree(spans: list[Span]) -> list[dict[str, Any]]:
    """Build a hierarchical span tree from a flat list of spans.

    Each node is a dict with keys: span, children, depth.
    Returns a list of root nodes (spans with no parent or orphaned parents).
    """
    if not spans:
        return []

    # Build lookup by span id
    nodes: dict[str, dict[str, Any]] = {}
    for span in spans:
        nodes[span.id] = {"span": span, "children": [], "depth": 0}

    # Wire parent-child relationships
    roots: list[dict[str, Any]] = []
    for span in spans:
        node = nodes[span.id]
        if span.parent_span_id and span.parent_span_id in nodes:
            nodes[span.parent_span_id]["children"].append(node)
        else:
            roots.append(node)

    # Set depths via BFS
    def _set_depth(node: dict[str, Any], depth: int) -> None:
        node["depth"] = depth
        for child in node["children"]:
            _set_depth(child, depth + 1)

    for root in roots:
        _set_depth(root, 0)

    return roots


class TraceQueryService:
    """Service for querying traces with search, filtering, and pagination."""

    async def list_traces(
        self,
        session: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        agent_id: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List traces with optional filtering, search, and pagination.

        Returns a dict with 'traces' (list of dicts) and 'total' (int).
        """
        # Base query
        base_query = select(Trace)
        count_query = select(func.count()).select_from(Trace)

        # Apply filters
        if status:
            base_query = base_query.where(Trace.status == status)
            count_query = count_query.where(Trace.status == status)

        if agent_id:
            base_query = base_query.where(Trace.agent_id == agent_id)
            count_query = count_query.where(Trace.agent_id == agent_id)

        if search:
            # Search by trace ID or agent name (join to Agent)
            base_query = base_query.join(Agent, Trace.agent_id == Agent.id).where(  # type: ignore[arg-type]
                (Trace.id.contains(search))  # type: ignore[attr-defined]
                | (Agent.name.contains(search))  # type: ignore[attr-defined]
            )
            count_query = count_query.join(Agent, Trace.agent_id == Agent.id).where(  # type: ignore[arg-type]
                (Trace.id.contains(search))  # type: ignore[attr-defined]
                | (Agent.name.contains(search))  # type: ignore[attr-defined]
            )

        # Get total count
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply ordering and pagination
        base_query = base_query.order_by(Trace.started_at.desc()).offset(offset).limit(limit)  # type: ignore[attr-defined]

        result = await session.execute(base_query)
        traces = result.scalars().all()

        # Get span counts per trace
        trace_ids = [t.id for t in traces]
        span_counts: dict[str, int] = {}
        if trace_ids:
            for tid in trace_ids:
                sc_result = await session.execute(select(func.count()).select_from(Span).where(Span.trace_id == tid))
                span_counts[tid] = sc_result.scalar() or 0

        # Get agent names
        agent_ids = list({t.agent_id for t in traces})
        agent_names: dict[str, str] = {}
        if agent_ids:
            agent_result = await session.execute(
                select(Agent).where(Agent.id.in_(agent_ids))  # type: ignore[attr-defined]
            )
            for agent in agent_result.scalars().all():
                agent_names[agent.id] = agent.name

        return {
            "traces": [
                {
                    "id": t.id,
                    "agent_id": t.agent_id,
                    "agent_name": agent_names.get(t.agent_id, "unknown"),
                    "session_id": t.session_id,
                    "status": t.status,
                    "started_at": t.started_at.isoformat() if t.started_at else None,
                    "ended_at": t.ended_at.isoformat() if t.ended_at else None,
                    "duration_ms": t.duration_ms,
                    "span_count": span_counts.get(t.id, 0),
                }
                for t in traces
            ],
            "total": total,
        }

    async def get_trace_detail(
        self,
        session: AsyncSession,
        trace_id: str,
    ) -> dict[str, Any] | None:
        """Get full trace detail including spans and span tree.

        Returns None if trace not found.
        """
        # Get trace
        result = await session.execute(select(Trace).where(Trace.id == trace_id))
        trace = result.scalar_one_or_none()
        if trace is None:
            return None

        # Get agent
        agent_result = await session.execute(select(Agent).where(Agent.id == trace.agent_id))
        agent = agent_result.scalar_one_or_none()

        # Get all spans for this trace
        spans_result = await session.execute(
            select(Span).where(Span.trace_id == trace_id).order_by(Span.started_at)  # type: ignore[arg-type]
        )
        spans = list(spans_result.scalars().all())

        # Build span tree
        span_tree = build_span_tree(spans)

        # Get tool calls for all spans in this trace
        span_ids = [s.id for s in spans]
        tool_calls_list: list[dict[str, Any]] = []
        if span_ids:
            tc_result = await session.execute(
                select(ToolCall).where(ToolCall.span_id.in_(span_ids))  # type: ignore[attr-defined]
            )
            tool_calls = tc_result.scalars().all()
            tool_calls_list = [
                {
                    "id": tc.id,
                    "span_id": tc.span_id,
                    "tool_name": tc.tool_name,
                    "tool_type": tc.tool_type,
                    "input_data": tc.input_data,
                    "output_data": tc.output_data,
                    "success": tc.success,
                    "duration_ms": tc.duration_ms,
                    "called_at": tc.called_at.isoformat() if tc.called_at else None,
                }
                for tc in tool_calls
            ]

        return {
            "id": trace.id,
            "agent_id": trace.agent_id,
            "agent_name": agent.name if agent else "unknown",
            "session_id": trace.session_id,
            "status": trace.status,
            "started_at": trace.started_at.isoformat() if trace.started_at else None,
            "ended_at": trace.ended_at.isoformat() if trace.ended_at else None,
            "duration_ms": trace.duration_ms,
            "spans": [
                {
                    "id": s.id,
                    "trace_id": s.trace_id,
                    "parent_span_id": s.parent_span_id,
                    "operation_name": s.operation_name,
                    "model": s.model,
                    "provider": s.provider,
                    "input_tokens": s.input_tokens,
                    "output_tokens": s.output_tokens,
                    "total_tokens": s.total_tokens,
                    "cost_usd": s.cost_usd,
                    "latency_ms": s.latency_ms,
                    "status": s.status,
                    "error_type": s.error_type,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                }
                for s in spans
            ],
            "span_tree": span_tree,
            "tool_calls": tool_calls_list,
        }

    async def get_tool_calls_for_span(
        self,
        session: AsyncSession,
        span_id: str,
    ) -> list[ToolCall]:
        """Get all tool calls for a specific span."""
        result = await session.execute(
            select(ToolCall).where(ToolCall.span_id == span_id).order_by(ToolCall.called_at)  # type: ignore[arg-type]
        )
        return list(result.scalars().all())

    async def compare_traces(
        self,
        session: AsyncSession,
        trace_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Get detail for multiple traces for side-by-side comparison.

        Returns a list of trace detail dicts (only for found traces).
        """
        results = []
        for tid in trace_ids:
            detail = await self.get_trace_detail(session, tid)
            if detail is not None:
                results.append(detail)
        return results
