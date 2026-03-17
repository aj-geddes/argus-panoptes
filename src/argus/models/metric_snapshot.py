"""MetricSnapshot model — pre-aggregated metrics for fast dashboard rendering."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class MetricSnapshot(SQLModel, table=True):
    """Pre-aggregated metrics for fast dashboard rendering."""

    id: int | None = Field(default=None, primary_key=True)
    agent_id: str = Field(foreign_key="agent.id", index=True)
    window_start: datetime = Field(index=True)
    window_size: str  # "1m", "5m", "1h", "1d"
    total_traces: int = 0
    successful_traces: int = 0
    failed_traces: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    tool_calls_total: int = 0
    tool_calls_failed: int = 0
