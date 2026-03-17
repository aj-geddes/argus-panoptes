"""Pydantic schemas for Agent API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AgentResponse(BaseModel):
    """Agent data returned by the API."""

    id: str
    name: str
    framework: str
    description: str | None = None
    tags: dict = {}
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    """Paginated list of agents."""

    agents: list[AgentResponse]
    total: int
