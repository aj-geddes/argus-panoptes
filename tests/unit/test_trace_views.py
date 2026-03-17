"""Tests for trace view routes — HTML responses for HTMX."""

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
async def seeded_view_client(config_file, tmp_path):
    """Create a test client with seeded trace data for view tests."""
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

    now = datetime.now(UTC)
    async with test_session_factory() as session:
        agent = Agent(id="agent-v1", name="view-test-agent", framework="openai")
        session.add(agent)
        await session.flush()

        trace = Trace(
            id="trace-v1",
            agent_id="agent-v1",
            status="completed",
            started_at=now - timedelta(minutes=5),
            ended_at=now,
            duration_ms=300000,
        )
        session.add(trace)
        await session.flush()

        root_span = Span(
            id="span-v1",
            trace_id="trace-v1",
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
            id="span-v2",
            trace_id="trace-v1",
            parent_span_id="span-v1",
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
        session.add_all([root_span, child_span])
        await session.flush()

        tool_call = ToolCall(
            span_id="span-v2",
            tool_name="calculator",
            tool_type="function",
            input_data={"expression": "2+2"},
            output_data={"result": 4},
            success=True,
            duration_ms=50,
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


class TestTraceListView:
    """Tests for GET /traces view route."""

    async def test_traces_page_renders_html(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Traces" in resp.text

    async def test_traces_page_contains_trace_row(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces")
        assert resp.status_code == 200
        assert "trace-v1" in resp.text

    async def test_traces_search_partial(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces/search", params={"q": "trace-v1"})
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "trace-v1" in resp.text

    async def test_traces_search_no_results(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces/search", params={"q": "nonexistent-xyz"})
        assert resp.status_code == 200
        assert "No traces found" in resp.text


class TestTraceDetailView:
    """Tests for GET /traces/{trace_id} view route."""

    async def test_trace_detail_page_renders(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces/trace-v1")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "trace-v1" in resp.text

    async def test_trace_detail_shows_span_tree(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces/trace-v1")
        assert resp.status_code == 200
        # Should contain span operation names
        assert "invoke_agent" in resp.text
        assert "tool_call" in resp.text

    async def test_trace_detail_not_found(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces/nonexistent")
        assert resp.status_code == 404

    async def test_trace_detail_shows_tool_call_panel(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces/trace-v1")
        assert resp.status_code == 200
        assert "calculator" in resp.text


class TestTraceCompareView:
    """Tests for GET /traces/compare view route."""

    async def test_compare_page_renders(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces/compare", params={"trace_ids": "trace-v1"})
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Compare" in resp.text

    async def test_compare_no_ids_shows_empty(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces/compare")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestToolCallPanel:
    """Tests for the tool call inspection partial."""

    async def test_tool_call_panel_returns_html(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces/spans/span-v2/tool-calls")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "calculator" in resp.text

    async def test_tool_call_panel_empty(self, seeded_view_client: AsyncClient) -> None:
        resp = await seeded_view_client.get("/traces/spans/span-v1/tool-calls")
        assert resp.status_code == 200
        assert "No tool calls" in resp.text
