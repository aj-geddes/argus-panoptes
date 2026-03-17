"""ToolCall model — represents a tool invocation within a span."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Column
from sqlmodel import JSON, Field, SQLModel


class ToolCall(SQLModel, table=True):
    """A tool call made during a span execution."""

    id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))
    span_id: str = Field(foreign_key="span.id", index=True)
    tool_name: str = Field(index=True)
    tool_type: str  # "function", "extension", "builtin"
    input_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    output_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    success: bool = True
    duration_ms: int = 0
    called_at: datetime
