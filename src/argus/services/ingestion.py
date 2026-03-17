"""Ingestion service — parses and stores incoming OTLP spans."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from argus.models.agent import Agent
from argus.models.span import Span
from argus.models.tool_call import ToolCall
from argus.models.trace import Trace
from argus.schemas.otlp import Attribute, IngestRequest
from argus.services.cost_calculator import CostCalculator

logger = logging.getLogger(__name__)

# Module-level cost calculator, initialized lazily from config
_cost_calculator: CostCalculator | None = None


def init_cost_calculator(cost_model_config: dict[str, Any]) -> None:
    """Initialize the cost calculator with pricing config."""
    global _cost_calculator
    _cost_calculator = CostCalculator(cost_model_config)
    logger.info("Cost calculator initialized")


def _get_attr(attributes: list[Attribute], key: str) -> str | int | bool | float | None:
    """Extract a value from an OTel attribute list by key."""
    for attr in attributes:
        if attr.key == key:
            val = attr.value
            if val.stringValue is not None:
                return val.stringValue
            if val.intValue is not None:
                return val.intValue
            if val.boolValue is not None:
                return val.boolValue
            if val.doubleValue is not None:
                return val.doubleValue
    return None


def _nano_to_datetime(nano_str: str) -> datetime:
    """Convert nanosecond Unix timestamp string to datetime."""
    try:
        ts = int(nano_str) / 1e9
        return datetime.fromtimestamp(ts, tz=UTC)
    except (ValueError, OSError):
        return datetime.now(UTC)


async def get_or_create_agent(
    session: AsyncSession,
    agent_name: str,
    framework: str = "custom",
) -> Agent:
    """Get an existing agent by name or create a new one."""
    stmt = select(Agent).where(Agent.name == agent_name)
    result = await session.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent is None:
        agent = Agent(name=agent_name, framework=framework)
        session.add(agent)
        await session.flush()
        logger.info("Auto-registered new agent: %s", agent_name)
    return agent


async def get_or_create_trace(
    session: AsyncSession,
    trace_id: str,
    agent_id: str,
    started_at: datetime,
    session_id: str | None = None,
) -> Trace:
    """Get an existing trace by ID or create a new one."""
    stmt = select(Trace).where(Trace.id == trace_id)
    result = await session.execute(stmt)
    trace = result.scalar_one_or_none()
    if trace is None:
        trace = Trace(
            id=trace_id,
            agent_id=agent_id,
            status="running",
            started_at=started_at,
            session_id=session_id,
        )
        session.add(trace)
        await session.flush()
    elif session_id and not trace.session_id:
        # Update session_id if not already set
        trace.session_id = session_id
        await session.flush()
    return trace


async def process_ingest_request(
    session: AsyncSession,
    request: IngestRequest,
) -> int:
    """Process an OTLP-like ingestion request and store spans. Returns span count."""
    total_spans = 0

    for resource_span in request.resourceSpans:
        # Extract agent name from resource attributes
        agent_name = str(_get_attr(resource_span.resource.attributes, "gen_ai.agent.name") or "unknown")

        for scope_span in resource_span.scopeSpans:
            # Detect framework from scope name if available
            framework = "custom"
            if scope_span.scope and scope_span.scope.name:
                framework = scope_span.scope.name

            for span_data in scope_span.spans:
                # Get or create agent (with framework hint from scope)
                agent = await get_or_create_agent(session, agent_name, framework=framework)

                # Parse timestamps
                started_at = _nano_to_datetime(span_data.startTimeUnixNano)
                ended_at = _nano_to_datetime(span_data.endTimeUnixNano) if span_data.endTimeUnixNano else None

                # Extract GenAI semantic convention attributes (v1.37)
                operation_name = str(_get_attr(span_data.attributes, "gen_ai.operation.name") or "unknown")
                model = _get_attr(span_data.attributes, "gen_ai.request.model")
                provider = _get_attr(span_data.attributes, "gen_ai.provider.name")
                input_tokens = _get_attr(span_data.attributes, "gen_ai.usage.input_tokens") or 0
                output_tokens = _get_attr(span_data.attributes, "gen_ai.usage.output_tokens") or 0
                conversation_id = _get_attr(span_data.attributes, "gen_ai.conversation.id")
                error_type = _get_attr(span_data.attributes, "error.type")

                # Get or create trace (with conversation_id -> session_id mapping)
                trace = await get_or_create_trace(
                    session,
                    span_data.traceId,
                    agent.id,
                    started_at,
                    session_id=str(conversation_id) if conversation_id else None,
                )

                # Calculate latency
                latency_ms = 0
                if ended_at and started_at:
                    latency_ms = int((ended_at - started_at).total_seconds() * 1000)

                # Calculate cost if pricing is available
                cost_usd = 0.0
                if _cost_calculator and model and provider:
                    cost_usd = _cost_calculator.calculate(
                        provider=str(provider),
                        model=str(model),
                        input_tokens=int(input_tokens),
                        output_tokens=int(output_tokens),
                    )

                # Determine span status from OTel status code or error.type attribute
                span_status = "ok"
                if error_type or (span_data.status and span_data.status.get("code") == "STATUS_CODE_ERROR"):
                    span_status = "error"

                # Create span
                span = Span(
                    id=span_data.spanId,
                    trace_id=trace.id,
                    parent_span_id=span_data.parentSpanId,
                    operation_name=operation_name,
                    model=str(model) if model else None,
                    provider=str(provider) if provider else None,
                    input_tokens=int(input_tokens),
                    output_tokens=int(output_tokens),
                    total_tokens=int(input_tokens) + int(output_tokens),
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    status=span_status,
                    error_type=str(error_type) if error_type else None,
                    started_at=started_at,
                    ended_at=ended_at,
                )
                session.add(span)

                # Handle tool calls if present (gen_ai.tool.name / gen_ai.tool.type)
                tool_name = _get_attr(span_data.attributes, "gen_ai.tool.name")
                if tool_name:
                    tool_type = str(_get_attr(span_data.attributes, "gen_ai.tool.type") or "function")
                    tool_call = ToolCall(
                        span_id=span.id,
                        tool_name=str(tool_name),
                        tool_type=tool_type,
                        success=span_status == "ok",
                        duration_ms=latency_ms,
                        called_at=started_at,
                    )
                    session.add(tool_call)

                total_spans += 1

    await session.commit()
    logger.info("Ingested %d spans", total_spans)

    # Broadcast SSE update for live dashboard
    if total_spans > 0:
        try:
            from argus.core.sse import dashboard_broadcaster

            await dashboard_broadcaster.publish({"event": "metrics", "data": {"spans_ingested": total_spans}})
        except Exception:
            logger.debug("SSE broadcast skipped (no event loop or subscribers)")

    return total_spans
