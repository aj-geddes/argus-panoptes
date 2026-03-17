"""Tests for all Pydantic schema modules to ensure full coverage."""

from __future__ import annotations

from datetime import UTC, datetime


class TestAgentSchemas:
    """Test suite for agent response schemas."""

    def test_agent_response(self) -> None:
        """AgentResponse should validate correct data."""
        from argus.schemas.agent import AgentResponse

        now = datetime.now(UTC)
        resp = AgentResponse(
            id="agent-1",
            name="test-agent",
            framework="langgraph",
            created_at=now,
            updated_at=now,
        )
        assert resp.id == "agent-1"
        assert resp.tags == {}

    def test_agent_list_response(self) -> None:
        """AgentListResponse should contain a list and total count."""
        from argus.schemas.agent import AgentListResponse, AgentResponse

        now = datetime.now(UTC)
        resp = AgentListResponse(
            agents=[
                AgentResponse(
                    id="a1",
                    name="agent-1",
                    framework="crewai",
                    created_at=now,
                    updated_at=now,
                )
            ],
            total=1,
        )
        assert len(resp.agents) == 1
        assert resp.total == 1


class TestTraceSchemas:
    """Test suite for trace response schemas."""

    def test_span_response(self) -> None:
        """SpanResponse should validate correct data."""
        from argus.schemas.trace import SpanResponse

        now = datetime.now(UTC)
        resp = SpanResponse(
            id="span-1",
            trace_id="trace-1",
            operation_name="chat",
            started_at=now,
        )
        assert resp.id == "span-1"
        assert resp.input_tokens == 0

    def test_trace_response(self) -> None:
        """TraceResponse should validate correct data."""
        from argus.schemas.trace import TraceResponse

        now = datetime.now(UTC)
        resp = TraceResponse(
            id="trace-1",
            agent_id="agent-1",
            status="completed",
            started_at=now,
        )
        assert resp.id == "trace-1"
        assert resp.spans == []

    def test_trace_list_response(self) -> None:
        """TraceListResponse should contain a list and total count."""
        from argus.schemas.trace import TraceListResponse, TraceResponse

        now = datetime.now(UTC)
        resp = TraceListResponse(
            traces=[
                TraceResponse(
                    id="t1",
                    agent_id="a1",
                    status="completed",
                    started_at=now,
                )
            ],
            total=1,
        )
        assert len(resp.traces) == 1


class TestConfigSchemas:
    """Test suite for config validation schemas."""

    def test_server_config_defaults(self) -> None:
        """ServerConfig should have sensible defaults."""
        from argus.schemas.config import ServerConfig

        cfg = ServerConfig()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8000
        assert cfg.workers == 4

    def test_database_config_defaults(self) -> None:
        """DatabaseConfig should have sensible defaults."""
        from argus.schemas.config import DatabaseConfig

        cfg = DatabaseConfig()
        assert "sqlite" in cfg.url
        assert cfg.pool_size == 10

    def test_ingestion_config_defaults(self) -> None:
        """IngestionConfig should have sensible defaults."""
        from argus.schemas.config import IngestionConfig

        cfg = IngestionConfig()
        assert cfg.otlp_enabled is True
        assert cfg.rest_enabled is True
        assert cfg.max_batch_size == 1000

    def test_argus_config_full(self) -> None:
        """ArgusConfig should compose all sub-configs."""
        from argus.schemas.config import ArgusConfig

        cfg = ArgusConfig(
            server={"host": "127.0.0.1", "port": 9000},
            database={"url": "postgresql+asyncpg://localhost/test"},
        )
        assert cfg.server.host == "127.0.0.1"
        assert cfg.server.port == 9000
        assert cfg.database.url == "postgresql+asyncpg://localhost/test"
        assert cfg.ingestion.otlp_enabled is True  # Default
