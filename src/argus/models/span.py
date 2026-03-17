"""Span model — represents a single operation within a trace."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlmodel import JSON, Field, SQLModel


class Span(SQLModel, table=True):
    """A span representing a single operation within a trace."""

    id: str = Field(primary_key=True)
    trace_id: str = Field(foreign_key="trace.id", index=True)
    parent_span_id: str | None = None
    operation_name: str  # "invoke_agent", "chat", "tool_call", "create_agent"
    model: str | None = None  # "gpt-5.4", "claude-opus-4-6", "gemini-3.1-pro", etc.
    provider: str | None = None  # "openai", "anthropic", "google", etc.
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    status: str = "ok"  # "ok", "error"
    error_type: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    started_at: datetime
    ended_at: datetime | None = None
