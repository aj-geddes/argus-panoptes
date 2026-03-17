"""Tests for agent registry service — auto-registration from spans."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_register_agent_creates_new(async_session) -> None:
    """Agent registry should create a new agent entry."""
    from argus.services.agent_registry import AgentRegistry

    registry = AgentRegistry()
    agent = await registry.register(
        session=async_session,
        name="new-registered-agent",
        framework="langgraph",
    )
    assert agent.name == "new-registered-agent"
    assert agent.framework == "langgraph"
    assert agent.id is not None


@pytest.mark.asyncio
async def test_register_agent_returns_existing(async_session) -> None:
    """Agent registry should return existing agent if name matches."""
    from argus.services.agent_registry import AgentRegistry

    registry = AgentRegistry()
    agent1 = await registry.register(async_session, "dup-agent", "crewai")
    await async_session.commit()
    agent2 = await registry.register(async_session, "dup-agent", "crewai")
    assert agent1.id == agent2.id


@pytest.mark.asyncio
async def test_register_agent_with_tags(async_session) -> None:
    """Agent registry should apply default tags from config."""
    from argus.services.agent_registry import AgentRegistry

    registry = AgentRegistry(default_tags={"environment": "test", "team": "ml"})
    agent = await registry.register(async_session, "tagged-agent", "openai")
    assert agent.tags["environment"] == "test"
    assert agent.tags["team"] == "ml"


@pytest.mark.asyncio
async def test_register_agent_updates_framework(async_session) -> None:
    """Agent registry should update framework if it changes."""
    from argus.services.agent_registry import AgentRegistry

    registry = AgentRegistry()
    agent1 = await registry.register(async_session, "framework-agent", "custom")
    await async_session.commit()
    agent2 = await registry.register(async_session, "framework-agent", "langgraph")
    assert agent2.framework == "langgraph"
    assert agent1.id == agent2.id


@pytest.mark.asyncio
async def test_list_agents(async_session) -> None:
    """Agent registry should list all registered agents."""
    from argus.services.agent_registry import AgentRegistry

    registry = AgentRegistry()
    await registry.register(async_session, "list-agent-1", "crewai")
    await registry.register(async_session, "list-agent-2", "openai")
    await async_session.commit()

    agents = await registry.list_agents(async_session)
    names = [a.name for a in agents]
    assert "list-agent-1" in names
    assert "list-agent-2" in names


@pytest.mark.asyncio
async def test_get_agent_by_id(async_session) -> None:
    """Agent registry should retrieve an agent by ID."""
    from argus.services.agent_registry import AgentRegistry

    registry = AgentRegistry()
    agent = await registry.register(async_session, "get-by-id-agent", "adk")
    await async_session.commit()

    found = await registry.get_agent(async_session, agent.id)
    assert found is not None
    assert found.name == "get-by-id-agent"


@pytest.mark.asyncio
async def test_get_agent_not_found(async_session) -> None:
    """Agent registry should return None for unknown agent ID."""
    from argus.services.agent_registry import AgentRegistry

    registry = AgentRegistry()
    found = await registry.get_agent(async_session, "nonexistent-id")
    assert found is None
