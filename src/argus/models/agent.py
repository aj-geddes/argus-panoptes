"""Agent model — represents a registered AI agent."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Column
from sqlmodel import JSON, Field, SQLModel


class Agent(SQLModel, table=True):
    """An AI agent registered in Argus."""

    id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))
    name: str = Field(index=True)
    framework: str  # "langgraph", "crewai", "openai", "adk", "custom"
    description: str | None = None
    tags: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
