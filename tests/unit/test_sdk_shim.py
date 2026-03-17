"""Tests for the Argus Python SDK shim."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from argus.sdk.reporter import ArgusReporter


class TestArgusReporter:
    """Tests for ArgusReporter SDK shim."""

    def test_init_defaults(self) -> None:
        reporter = ArgusReporter()
        assert reporter._endpoint == "http://localhost:8000"
        assert reporter._agent_name == "default"

    def test_init_custom(self) -> None:
        reporter = ArgusReporter(endpoint="http://example.com:9000", agent_name="my-agent")
        assert reporter._endpoint == "http://example.com:9000"
        assert reporter._agent_name == "my-agent"

    def test_build_otlp_payload(self) -> None:
        reporter = ArgusReporter(agent_name="test-bot")
        payload = reporter._build_otlp_payload(
            operation="chat",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            latency_ms=1500,
        )

        assert "resourceSpans" in payload
        resource_spans = payload["resourceSpans"]
        assert len(resource_spans) == 1

        # Check resource attributes
        resource_attrs = resource_spans[0]["resource"]["attributes"]
        agent_attr = next(a for a in resource_attrs if a["key"] == "gen_ai.agent.name")
        assert agent_attr["value"]["stringValue"] == "test-bot"

        # Check span attributes
        spans = resource_spans[0]["scopeSpans"][0]["spans"]
        assert len(spans) == 1
        span = spans[0]
        assert span["name"] == "chat gpt-4o"

        attrs = {a["key"]: a["value"] for a in span["attributes"]}
        assert attrs["gen_ai.operation.name"]["stringValue"] == "chat"
        assert attrs["gen_ai.request.model"]["stringValue"] == "gpt-4o"
        assert attrs["gen_ai.provider.name"]["stringValue"] == "openai"
        assert attrs["gen_ai.usage.input_tokens"]["intValue"] == 100
        assert attrs["gen_ai.usage.output_tokens"]["intValue"] == 50

    def test_build_otlp_payload_with_tool(self) -> None:
        reporter = ArgusReporter(agent_name="tool-bot")
        payload = reporter._build_otlp_payload(
            operation="tool_call",
            model="gpt-4o",
            provider="openai",
            input_tokens=0,
            output_tokens=0,
            latency_ms=200,
            tool_name="calculator",
            tool_type="function",
        )
        spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
        attrs = {a["key"]: a["value"] for a in spans[0]["attributes"]}
        assert attrs["gen_ai.tool.name"]["stringValue"] == "calculator"
        assert attrs["gen_ai.tool.type"]["stringValue"] == "function"

    def test_build_otlp_payload_with_error(self) -> None:
        reporter = ArgusReporter()
        payload = reporter._build_otlp_payload(
            operation="chat",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=0,
            latency_ms=5000,
            error_type="TimeoutError",
        )
        spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
        attrs = {a["key"]: a["value"] for a in spans[0]["attributes"]}
        assert attrs["error.type"]["stringValue"] == "TimeoutError"

    def test_build_otlp_payload_with_parent_span(self) -> None:
        reporter = ArgusReporter()
        payload = reporter._build_otlp_payload(
            operation="chat",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            latency_ms=1000,
            parent_span_id="parent-123",
            trace_id="trace-456",
        )
        span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["parentSpanId"] == "parent-123"
        assert span["traceId"] == "trace-456"

    def test_build_otlp_payload_timestamps(self) -> None:
        reporter = ArgusReporter()
        payload = reporter._build_otlp_payload(
            operation="chat",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            latency_ms=1500,
        )
        span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        start = int(span["startTimeUnixNano"])
        end = int(span["endTimeUnixNano"])
        # Latency should roughly match 1500ms
        diff_ms = (end - start) / 1e6
        assert 1400 < diff_ms < 1600

    async def test_report_span_calls_httpx(self) -> None:
        reporter = ArgusReporter(endpoint="http://test:8000", agent_name="sdk-bot")
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "spans_accepted": 1}

        with patch.object(reporter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            await reporter.report_span(
                operation="chat",
                model="gpt-4o",
                provider="openai",
                input_tokens=100,
                output_tokens=50,
                latency_ms=1500,
            )
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://test:8000/v1/traces"

    async def test_close_closes_client(self) -> None:
        reporter = ArgusReporter()
        with patch.object(reporter, "_client") as mock_client:
            mock_client.aclose = AsyncMock()
            await reporter.close()
            mock_client.aclose.assert_called_once()

    def test_context_manager_protocol(self) -> None:
        """Verify the reporter supports async context manager."""
        reporter = ArgusReporter()
        assert hasattr(reporter, "__aenter__")
        assert hasattr(reporter, "__aexit__")
