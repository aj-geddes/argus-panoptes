"""Pydantic models for OTel-compatible OTLP JSON trace ingestion."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AttributeValue(BaseModel):
    """An attribute value that can be a string, int, bool, or float."""

    stringValue: str | None = None
    intValue: int | None = None
    boolValue: bool | None = None
    doubleValue: float | None = None


class Attribute(BaseModel):
    """A key-value attribute pair."""

    key: str
    value: AttributeValue


class Resource(BaseModel):
    """Resource descriptor with attributes."""

    attributes: list[Attribute] = Field(default_factory=list)


class SpanData(BaseModel):
    """A single span in OTLP format."""

    traceId: str
    spanId: str
    parentSpanId: str | None = None
    name: str = ""
    attributes: list[Attribute] = Field(default_factory=list)
    startTimeUnixNano: str = "0"
    endTimeUnixNano: str | None = None
    status: dict[str, str] | None = None


class InstrumentationScope(BaseModel):
    """Instrumentation scope metadata."""

    name: str = ""
    version: str = ""


class ScopeSpans(BaseModel):
    """A collection of spans from a single instrumentation scope."""

    scope: InstrumentationScope | None = None
    spans: list[SpanData] = Field(default_factory=list)


class ResourceSpans(BaseModel):
    """Spans associated with a resource."""

    resource: Resource = Field(default_factory=Resource)
    scopeSpans: list[ScopeSpans] = Field(default_factory=list)


class IngestRequest(BaseModel):
    """Top-level OTLP JSON traces request payload."""

    resourceSpans: list[ResourceSpans]
