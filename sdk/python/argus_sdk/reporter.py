"""Argus SDK reporter — lightweight shim for frameworks without OTel instrumentation.

This is a standalone package that can be installed independently of the Argus server.

Usage:
    async with ArgusReporter(endpoint="http://localhost:8000", agent_name="my-bot") as reporter:
        await reporter.report_span(
            operation="chat",
            model="gpt-4o",
            provider="openai",
            input_tokens=500,
            output_tokens=200,
            latency_ms=1500,
        )

    # Or use decorators for automatic reporting:
    @reporter.trace_function
    async def my_agent_step():
        ...
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


class ArgusReporter:
    """Lightweight SDK for reporting spans to Argus from non-OTel frameworks.

    Builds OTLP-compatible JSON payloads and sends them to the Argus ingestion endpoint.
    Supports async context manager protocol for clean resource management.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:8000",
        agent_name: str = "default",
    ) -> None:
        self._endpoint = endpoint
        self._agent_name = agent_name
        self._client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self) -> ArgusReporter:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    def _build_otlp_payload(
        self,
        operation: str,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        *,
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        tool_name: str | None = None,
        tool_type: str | None = None,
        error_type: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Build an OTLP-compatible JSON payload for the ingestion endpoint."""
        now = datetime.now(UTC)
        end_ns = int(now.timestamp() * 1e9)
        start_ns = int((now.timestamp() - latency_ms / 1000) * 1e9)

        if trace_id is None:
            trace_id = uuid4().hex[:32]
        if span_id is None:
            span_id = uuid4().hex[:16]

        attributes: list[dict[str, Any]] = [
            {"key": "gen_ai.operation.name", "value": {"stringValue": operation}},
            {"key": "gen_ai.request.model", "value": {"stringValue": model}},
            {"key": "gen_ai.provider.name", "value": {"stringValue": provider}},
            {"key": "gen_ai.usage.input_tokens", "value": {"intValue": input_tokens}},
            {"key": "gen_ai.usage.output_tokens", "value": {"intValue": output_tokens}},
        ]

        if tool_name:
            attributes.append({"key": "gen_ai.tool.name", "value": {"stringValue": tool_name}})
        if tool_type:
            attributes.append({"key": "gen_ai.tool.type", "value": {"stringValue": tool_type}})
        if error_type:
            attributes.append({"key": "error.type", "value": {"stringValue": error_type}})
        if conversation_id:
            attributes.append({"key": "gen_ai.conversation.id", "value": {"stringValue": conversation_id}})

        span_data: dict[str, Any] = {
            "traceId": trace_id,
            "spanId": span_id,
            "name": f"{operation} {model}",
            "attributes": attributes,
            "startTimeUnixNano": str(start_ns),
            "endTimeUnixNano": str(end_ns),
        }

        if parent_span_id:
            span_data["parentSpanId"] = parent_span_id

        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "gen_ai.agent.name", "value": {"stringValue": self._agent_name}},
                        ]
                    },
                    "scopeSpans": [{"spans": [span_data]}],
                }
            ]
        }

    async def report_span(
        self,
        operation: str,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Report a single span to the Argus ingestion endpoint.

        Returns the response JSON from Argus.
        """
        payload = self._build_otlp_payload(
            operation=operation,
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            **kwargs,
        )

        response = await self._client.post(
            f"{self._endpoint}/v1/traces",
            json=payload,
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result
