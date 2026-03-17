"""Tests for trace API routes — JSON endpoints for trace queries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from argus.models.agent import Agent
from argus.models.span import Span
from argus.models.tool_call import ToolCall
from argus.models.trace import Trace


@pytest.fixture()
async def seeded_client(config_file, tmp_path):
    """Create a test client with seeded trace data."""
    import os
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport, AsyncClient

    import argus.models  # noqa: F401

    os.environ["ARGUS_CONFIG_PATH"] = str(config_file)

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Seed data
    now = datetime.now(UTC)
    async with test_session_factory() as session:
        agent = Agent(id="agent-1", name="test-agent", framework="openai")
        session.add(agent)
        await session.flush()

        trace1 = Trace(
            id="trace-001",
            agent_id="agent-1",
            status="completed",
            started_at=now - timedelta(minutes=5),
            ended_at=now,
            duration_ms=300000,
        )
        trace2 = Trace(
            id="trace-002",
            agent_id="agent-1",
            status="failed",
            started_at=now - timedelta(minutes=10),
            ended_at=now - timedelta(minutes=8),
            duration_ms=120000,
        )
        session.add_all([trace1, trace2])
        await session.flush()

        root_span = Span(
            id="span-001",
            trace_id="trace-001",
            parent_span_id=None,
            operation_name="invoke_agent",
            model="gpt-4o",
            provider="openai",
            input_tokens=500,
            output_tokens=200,
            total_tokens=700,
            cost_usd=0.003,
            latency_ms=1500,
            status="ok",
            started_at=now - timedelta(minutes=5),
            ended_at=now - timedelta(minutes=4),
        )
        child_span = Span(
            id="span-002",
            trace_id="trace-001",
            parent_span_id="span-001",
            operation_name="tool_call",
            model=None,
            provider=None,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            latency_ms=200,
            status="ok",
            started_at=now - timedelta(minutes=4, seconds=30),
            ended_at=now - timedelta(minutes=4, seconds=20),
        )
        error_span = Span(
            id="span-003",
            trace_id="trace-002",
            parent_span_id=None,
            operation_name="chat",
            model="claude-sonnet-4",
            provider="anthropic",
            input_tokens=1000,
            output_tokens=0,
            total_tokens=1000,
            latency_ms=5000,
            status="error",
            error_type="TimeoutError",
            started_at=now - timedelta(minutes=10),
            ended_at=now - timedelta(minutes=8),
        )
        session.add_all([root_span, child_span, error_span])
        await session.flush()

        tool_call = ToolCall(
            span_id="span-002",
            tool_name="web_search",
            tool_type="function",
            input_data={"query": "test"},
            output_data={"results": []},
            success=True,
            duration_ms=200,
            called_at=now - timedelta(minutes=4, seconds=30),
        )
        session.add(tool_call)
        await session.commit()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    from argus.core.database import get_session
    from argus.main import create_app

    app = create_app(config_path=str(config_file))
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await test_engine.dispose()
    app.dependency_overrides.clear()


class TestTraceListAPI:
    """Tests for GET /api/v1/traces endpoint."""

    async def test_list_traces(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get("/api/v1/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert "traces" in data
        assert "total" in data
        assert data["total"] == 2

    async def test_list_traces_with_limit(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get("/api/v1/traces", params={"limit": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["traces"]) == 1
        assert data["total"] == 2

    async def test_list_traces_with_status_filter(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get("/api/v1/traces", params={"status": "failed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["traces"][0]["status"] == "failed"

    async def test_list_traces_with_search(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get("/api/v1/traces", params={"search": "trace-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    async def test_list_traces_with_agent_id_filter(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get("/api/v1/traces", params={"agent_id": "agent-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2


class TestTraceDetailAPI:
    """Tests for GET /api/v1/traces/{trace_id} endpoint."""

    async def test_get_trace_detail(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get("/api/v1/traces/trace-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "trace-001"
        assert len(data["spans"]) == 2
        assert "span_tree" in data

    async def test_get_trace_not_found(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get("/api/v1/traces/nonexistent")
        assert resp.status_code == 404

    async def test_trace_detail_includes_tool_calls(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get("/api/v1/traces/trace-001")
        data = resp.json()
        assert "tool_calls" in data
        assert len(data["tool_calls"]) == 1


class TestTraceCompareAPI:
    """Tests for GET /api/v1/traces/compare endpoint."""

    async def test_compare_two_traces(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get(
            "/api/v1/traces/compare",
            params={"trace_ids": "trace-001,trace-002"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "traces" in data
        assert len(data["traces"]) == 2

    async def test_compare_missing_param(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get("/api/v1/traces/compare")
        assert resp.status_code == 400

    async def test_compare_partial_not_found(self, seeded_client: AsyncClient) -> None:
        resp = await seeded_client.get(
            "/api/v1/traces/compare",
            params={"trace_ids": "trace-001,nonexistent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["traces"]) == 1
