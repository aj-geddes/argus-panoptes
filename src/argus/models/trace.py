"""Trace model — represents a single agent execution trace."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column
from sqlmodel import JSON, Field, SQLModel


class Trace(SQLModel, table=True):
    """A trace representing a single agent execution."""

    id: str = Field(primary_key=True)
    agent_id: str = Field(foreign_key="agent.id", index=True)
    session_id: str | None = Field(default=None, index=True)
    status: str  # "running", "completed", "failed", "timeout"
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None
    metadata_: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON),
    )
