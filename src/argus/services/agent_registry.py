"""Agent registry service — auto-registration and lookup."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from argus.models.agent import Agent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Manages agent registration, lookup, and auto-registration from spans."""

    def __init__(self, default_tags: dict[str, Any] | None = None) -> None:
        self._default_tags = default_tags or {}

    async def register(
        self,
        session: AsyncSession,
        name: str,
        framework: str = "custom",
        description: str | None = None,
    ) -> Agent:
        """Register an agent or return existing one. Updates framework if changed."""
        stmt = select(Agent).where(Agent.name == name)
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()

        if agent is None:
            agent = Agent(
                name=name,
                framework=framework,
                description=description,
                tags=dict(self._default_tags),
            )
            session.add(agent)
            await session.flush()
            logger.info("Registered new agent: %s (%s)", name, framework)
        else:
            # Update framework if it changed
            if agent.framework != framework:
                agent.framework = framework
                agent.updated_at = datetime.now(UTC)
                await session.flush()
                logger.info("Updated agent %s framework to %s", name, framework)

        return agent

    async def list_agents(self, session: AsyncSession) -> list[Agent]:
        """List all registered agents."""
        stmt = select(Agent).order_by(Agent.name)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_agent(self, session: AsyncSession, agent_id: str) -> Agent | None:
        """Get a single agent by ID."""
        stmt = select(Agent).where(Agent.id == agent_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
