"""Tests for Pydantic schemas used in API validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestOTLPSchemas:
    """Test OTel-compatible Pydantic schemas for ingestion."""

    def test_valid_attribute_value_string(self) -> None:
        """AttributeValue should accept stringValue."""
        from argus.schemas.otlp import AttributeValue

        val = AttributeValue(stringValue="hello")
        assert val.stringValue == "hello"

    def test_valid_attribute_value_int(self) -> None:
        """AttributeValue should accept intValue."""
        from argus.schemas.otlp import AttributeValue

        val = AttributeValue(intValue=42)
        assert val.intValue == 42

    def test_valid_span_data(self) -> None:
        """SpanData should validate a minimal span."""
        from argus.schemas.otlp import SpanData

        span = SpanData(
            traceId="trace-123",
            spanId="span-456",
            name="test span",
            attributes=[],
            startTimeUnixNano="1710000000000000000",
            endTimeUnixNano="1710000001000000000",
        )
        assert span.traceId == "trace-123"

    def test_ingest_request_validation(self) -> None:
        """IngestRequest should validate the full OTLP-like payload."""
        from argus.schemas.otlp import IngestRequest

        request = IngestRequest(
            resourceSpans=[
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "gen_ai.agent.name",
                                "value": {"stringValue": "agent-1"},
                            }
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "t1",
                                    "spanId": "s1",
                                    "name": "op",
                                    "attributes": [],
                                    "startTimeUnixNano": "0",
                                    "endTimeUnixNano": "1",
                                }
                            ]
                        }
                    ],
                }
            ]
        )
        assert len(request.resourceSpans) == 1

    def test_ingest_request_rejects_missing_resource_spans(self) -> None:
        """IngestRequest should reject payload without resourceSpans."""
        from argus.schemas.otlp import IngestRequest

        with pytest.raises(ValidationError):
            IngestRequest()  # type: ignore[call-arg]
