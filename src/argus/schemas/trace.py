"""Pydantic schemas for Trace API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SpanResponse(BaseModel):
    """Span data returned by the API."""

    id: str
    trace_id: str
    parent_span_id: str | None = None
    operation_name: str
    model: str | None = None
    provider: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    status: str = "ok"
    started_at: datetime
    ended_at: datetime | None = None


class TraceResponse(BaseModel):
    """Trace data returned by the API."""

    id: str
    agent_id: str
    session_id: str | None = None
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None
    spans: list[SpanResponse] = []


class TraceListResponse(BaseModel):
    """Paginated list of traces."""

    traces: list[TraceResponse]
    total: int
