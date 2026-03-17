---
title: "Python SDK"
description: "Integrate Argus Panoptes with any Python agent framework using the lightweight SDK."
layout: page
---

The Argus Python SDK provides a simple, non-blocking reporter for frameworks
that do not have native OpenTelemetry support. It batches spans and sends them
asynchronously to Argus using the same OTLP-compatible REST API.

## Installation

```bash
pip install argus-panoptes-sdk
```

Or install directly from the repository:

```bash
pip install "git+https://github.com/aj-geddes/argus-panoptes.git#subdirectory=sdk/python"
```

---

## Basic Usage

```python
from argus.sdk.reporter import ArgusReporter

reporter = ArgusReporter(
    endpoint="http://localhost:8000",
    agent_name="my-agent",
    agent_version="1.0.0",
    api_key="your-api-key",       # optional
    flush_interval_seconds=5,     # batch flush interval
    tags={"environment": "production", "team": "ml"},
)

# Report a single LLM call
await reporter.report_span(
    operation="chat",
    model="gpt-4o",
    provider="openai",
    input_tokens=512,
    output_tokens=128,
    latency_ms=1200,
    has_error=False,
)

# Report a tool call
await reporter.report_span(
    operation="tool_call",
    model="gpt-4o",
    provider="openai",
    input_tokens=200,
    output_tokens=50,
    latency_ms=450,
    tool_calls=[
        {"name": "web_search", "success": True, "duration_ms": 380}
    ],
)
```

---

## Context Manager

Use `async with` to ensure the final batch is flushed on exit:

```python
async with ArgusReporter(
    endpoint="http://localhost:8000",
    agent_name="batch-agent",
) as reporter:
    for query in queries:
        result = await run_agent(query)
        await reporter.report_span(
            operation="chat",
            model="claude-sonnet-4-6",
            provider="anthropic",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.duration_ms,
        )
# Remaining spans are flushed automatically on __aexit__
```

---

## Framework Integration Matrix

| Framework | Recommended Approach | Complexity |
|-----------|---------------------|------------|
| LangGraph | `OTEL_EXPORTER_OTLP_ENDPOINT` env var | Low |
| CrewAI | Native OTel instrumentation | Low |
| OpenAI Agents SDK | OTel Python SDK wrapper | Low |
| Google ADK | OTel collector | Low |
| PydanticAI | Native OTel support | Low |
| AutoGen | `opentelemetry-instrumentation-autogen` | Medium |
| Semantic Kernel | Microsoft OTel integration | Medium |
| Custom / raw LLM calls | Argus Python SDK | Low |

---

## LangGraph Integration

LangGraph emits OpenTelemetry spans via LangSmith's OTel exporter. Point it at Argus:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:8000/v1/traces"
export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
export LANGCHAIN_TRACING_V2="true"
```

Or in Python:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="http://localhost:8000/v1/traces")
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# Now your LangGraph agent automatically sends spans to Argus
from langgraph.graph import StateGraph

graph = StateGraph(...)
# ... define nodes and edges
app = graph.compile()
result = await app.ainvoke({"input": "What is the capital of France?"})
```

---

## CrewAI Integration

CrewAI has built-in OTel instrumentation. Configure it to export to Argus:

```python
import os
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:8000/v1/traces"
os.environ["OTEL_SERVICE_NAME"] = "my-crewai-app"

from crewai import Agent, Task, Crew
from crewai.telemetry import Telemetry

# CrewAI automatically instruments LLM calls when OTel is configured
researcher = Agent(
    role="Research Analyst",
    goal="Find accurate information",
    backstory="Expert at research and analysis",
    llm="gpt-4o",
)

task = Task(
    description="Research the latest developments in AI agent frameworks",
    expected_output="A summary of key developments",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task])
result = crew.kickoff()
```

---

## OpenAI Agents SDK Integration

For the OpenAI Agents SDK, use the OTel instrumentation wrapper:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

# Configure OTel to export to Argus
provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="http://localhost:8000/v1/traces")
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# Instrument the OpenAI client
OpenAIInstrumentor().instrument()

import openai
from agents import Agent, Runner

agent = Agent(
    name="assistant",
    instructions="You are a helpful assistant.",
    model="gpt-4o",
)

result = await Runner.run(agent, "What is 2 + 2?")
# Spans are automatically captured and sent to Argus
```

---

## Custom Agent Integration (Direct SDK)

For fully custom agents or any framework not listed above:

```python
import asyncio
import time
from argus.sdk.reporter import ArgusReporter

reporter = ArgusReporter(
    endpoint="http://localhost:8000",
    agent_name="custom-research-bot",
    agent_version="2.0.0",
    tags={"team": "research", "environment": "production"},
)

async def run_research_query(query: str) -> dict:
    start = time.perf_counter()
    try:
        # Your LLM call here
        response = await my_llm_client.chat(
            model="gpt-4o",
            messages=[{"role": "user", "content": query}],
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        await reporter.report_span(
            operation="chat",
            model="gpt-4o",
            provider="openai",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            latency_ms=latency_ms,
            has_error=False,
            trace_id=response.id,
        )
        return {"answer": response.choices[0].message.content}

    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        await reporter.report_span(
            operation="chat",
            model="gpt-4o",
            provider="openai",
            input_tokens=0,
            output_tokens=0,
            latency_ms=latency_ms,
            has_error=True,
            error_type=type(exc).__name__,
        )
        raise
```

---

## Reporter API Reference

### `ArgusReporter(endpoint, agent_name, **kwargs)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | str | required | Base URL of the Argus server |
| `agent_name` | str | required | Name for agent auto-registration |
| `agent_version` | str | `"unknown"` | Agent version string |
| `api_key` | str | `None` | API key (if auth is enabled) |
| `flush_interval_seconds` | float | `5.0` | How often to flush the batch queue |
| `max_batch_size` | int | `100` | Maximum spans per HTTP request |
| `tags` | dict | `{}` | Tags attached to all spans |
| `timeout_seconds` | float | `10.0` | HTTP request timeout |

### `await reporter.report_span(**kwargs)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `operation` | str | GenAI operation: `chat`, `embeddings`, `tool_call`, `completion` |
| `model` | str | Model name matching the cost model config |
| `provider` | str | Provider: `openai`, `anthropic`, `google`, etc. |
| `input_tokens` | int | Number of input / prompt tokens |
| `output_tokens` | int | Number of output / completion tokens |
| `latency_ms` | int | Request duration in milliseconds |
| `has_error` | bool | Whether the call resulted in an error |
| `error_type` | str | Exception class name (if has_error=True) |
| `trace_id` | str | Optional trace ID for grouping spans |
| `span_id` | str | Optional span ID |
| `parent_span_id` | str | Optional parent span ID |
| `tool_calls` | list | List of `{name, success, duration_ms}` dicts |
| `attributes` | dict | Additional arbitrary attributes |
