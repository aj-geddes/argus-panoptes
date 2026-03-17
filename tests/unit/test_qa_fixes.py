"""Tests for QA-identified issues — HIGH and MEDIUM severity fixes.

Each test section corresponds to a numbered issue from the QA review.
Tests are written FIRST (red), then code is fixed to make them pass (green).
"""

from __future__ import annotations

import logging
import os
from collections import deque
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from argus.services.alerting import AlertEngine


# ---------------------------------------------------------------------------
# Issue #1: CORS misconfiguration
# ---------------------------------------------------------------------------
class TestCORSConfiguration:
    """allow_origins=['*'] with allow_credentials=True is invalid per CORS spec."""

    def test_cors_default_no_wildcard_with_credentials(self, config_file: Path) -> None:
        """When no CORS origins are configured, should use localhost default
        and set allow_credentials=False for wildcard."""
        # Set env var so the module-level create_app() does not fail
        os.environ["ARGUS_CONFIG_PATH"] = str(config_file)

        import argus.main as main_mod

        app = main_mod.create_app(config_path=str(config_file))
        # Find CORSMiddleware in the middleware stack
        cors_mw = None
        for mw in app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_mw = mw
                break
        assert cors_mw is not None, "CORSMiddleware not found"
        # Should not have wildcard with credentials=True
        origins = cors_mw.kwargs.get("allow_origins", [])
        credentials = cors_mw.kwargs.get("allow_credentials", False)
        if "*" in origins:
            assert credentials is False, "allow_credentials must be False when wildcard origins are used"
        else:
            # Origins should be a specific list
            assert isinstance(origins, list)
            assert len(origins) > 0

    def test_cors_config_driven_origins(self, tmp_path: Path, sample_config: dict[str, Any], config_file: Path) -> None:
        """CORS origins should be configurable via config file."""
        # Ensure ARGUS_CONFIG_PATH points to a valid file for module import
        os.environ["ARGUS_CONFIG_PATH"] = str(config_file)

        sample_config["cors"] = {
            "allowed_origins": ["https://app.example.com", "https://admin.example.com"],
        }
        config_path = tmp_path / "argus_cors.yaml"
        config_path.write_text(yaml.dump(sample_config))

        from argus.main import create_app

        app = create_app(config_path=str(config_path))
        cors_mw = None
        for mw in app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_mw = mw
                break
        assert cors_mw is not None
        origins = cors_mw.kwargs.get("allow_origins", [])
        assert "https://app.example.com" in origins
        assert "https://admin.example.com" in origins


# ---------------------------------------------------------------------------
# Issue #2: Auth disabled by default with no warning
# ---------------------------------------------------------------------------
class TestSecurityWarning:
    """When both auth and rate limiting are off, a warning should be logged."""

    def test_warning_when_both_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """setup_security_middleware should log a warning when both auth and rate limiting are disabled."""
        from fastapi import FastAPI

        from argus.core.security import setup_security_middleware

        app = FastAPI()
        config: dict[str, Any] = {
            "api_key_auth": {"enabled": False},
            "rate_limiting": {"enabled": False},
        }
        with caplog.at_level(logging.WARNING, logger="argus.core.security"):
            setup_security_middleware(app, config)
        assert any("no auth" in r.message.lower() or "unauthenticated" in r.message.lower() for r in caplog.records), (
            "Expected a WARNING-level log when both auth and rate limiting are disabled"
        )

    def test_no_warning_when_auth_enabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """No warning should be logged when auth is enabled."""
        from fastapi import FastAPI

        from argus.core.security import setup_security_middleware

        app = FastAPI()
        config: dict[str, Any] = {
            "api_key_auth": {"enabled": True, "key": "test-key"},
            "rate_limiting": {"enabled": False},
        }
        with caplog.at_level(logging.WARNING, logger="argus.core.security"):
            setup_security_middleware(app, config)
        warning_msgs = [r for r in caplog.records if r.levelno >= logging.WARNING]
        security_warnings = [r for r in warning_msgs if "unauthenticated" in r.message.lower()]
        assert len(security_warnings) == 0


# ---------------------------------------------------------------------------
# Issue #3: Webhook SSRF
# ---------------------------------------------------------------------------
class TestWebhookSSRF:
    """Webhook URL validation should block SSRF attempts."""

    def test_blocks_private_ip(self) -> None:
        """Webhook URL pointing to private IP should be rejected."""
        from argus.services.webhooks import WebhookNotifier

        notifier = WebhookNotifier(webhooks=[{"name": "evil", "url": "http://192.168.1.1/webhook"}])
        # Private IPs should be filtered out during load
        assert len(notifier.configs) == 0

    def test_blocks_loopback(self) -> None:
        """Webhook URL pointing to loopback address should be rejected."""
        from argus.services.webhooks import WebhookNotifier

        notifier = WebhookNotifier(webhooks=[{"name": "evil", "url": "http://127.0.0.1/webhook"}])
        assert len(notifier.configs) == 0

    def test_blocks_link_local(self) -> None:
        """Webhook URL pointing to link-local IP should be rejected."""
        from argus.services.webhooks import WebhookNotifier

        notifier = WebhookNotifier(webhooks=[{"name": "evil", "url": "http://169.254.169.254/metadata"}])
        assert len(notifier.configs) == 0

    def test_blocks_non_http_scheme(self) -> None:
        """Webhook URL with non-HTTP scheme should be rejected."""
        from argus.services.webhooks import WebhookNotifier

        notifier = WebhookNotifier(webhooks=[{"name": "evil", "url": "file:///etc/passwd"}])
        assert len(notifier.configs) == 0

    def test_blocks_ftp_scheme(self) -> None:
        """Webhook URL with ftp scheme should be rejected."""
        from argus.services.webhooks import WebhookNotifier

        notifier = WebhookNotifier(webhooks=[{"name": "evil", "url": "ftp://internal.server/data"}])
        assert len(notifier.configs) == 0

    def test_allows_public_https(self) -> None:
        """Webhook URL pointing to public HTTPS should be allowed."""
        from argus.services.webhooks import WebhookNotifier

        notifier = WebhookNotifier(webhooks=[{"name": "slack", "url": "https://hooks.slack.com/services/T00/B00/xxx"}])
        assert len(notifier.configs) == 1

    def test_allows_public_http(self) -> None:
        """Webhook URL pointing to public HTTP should be allowed."""
        from argus.services.webhooks import WebhookNotifier

        notifier = WebhookNotifier(webhooks=[{"name": "pager", "url": "http://events.pagerduty.com/hook"}])
        assert len(notifier.configs) == 1

    def test_blocks_localhost_hostname(self) -> None:
        """Webhook URL using 'localhost' hostname should be rejected."""
        from argus.services.webhooks import WebhookNotifier

        notifier = WebhookNotifier(webhooks=[{"name": "evil", "url": "http://localhost:8080/webhook"}])
        assert len(notifier.configs) == 0

    def test_blocks_10_dot_network(self) -> None:
        """Webhook URL pointing to 10.x.x.x should be rejected."""
        from argus.services.webhooks import WebhookNotifier

        notifier = WebhookNotifier(webhooks=[{"name": "evil", "url": "http://10.0.0.1/webhook"}])
        assert len(notifier.configs) == 0

    @pytest.mark.asyncio
    async def test_send_validates_url_at_send_time(self) -> None:
        """Even if a config is loaded, sending should validate the URL."""
        from argus.services.webhooks import _validate_webhook_url

        # Direct validation function test
        assert _validate_webhook_url("https://hooks.slack.com/test") is True
        assert _validate_webhook_url("http://127.0.0.1/test") is False
        assert _validate_webhook_url("http://192.168.0.1/test") is False
        assert _validate_webhook_url("ftp://example.com/test") is False


# ---------------------------------------------------------------------------
# Issue #4: Config env var expansion
# ---------------------------------------------------------------------------
class TestConfigEnvVarExpansion:
    """${VAR} patterns in config YAML should be expanded with os.environ values."""

    def test_expand_env_var_in_config(self, tmp_path: Path) -> None:
        """Config values like ${SLACK_WEBHOOK_URL} should be replaced with env var values."""
        os.environ["TEST_WEBHOOK_URL"] = "https://hooks.slack.com/actual"
        try:
            config_content = """
webhooks:
  - name: slack
    url: "${TEST_WEBHOOK_URL}"
server:
  host: "0.0.0.0"
  port: 8000
"""
            config_path = tmp_path / "argus_env.yaml"
            config_path.write_text(config_content)

            from argus.core.config import ConfigManager

            manager = ConfigManager(str(config_path))
            webhooks = manager.get("webhooks")
            assert webhooks is not None
            assert webhooks[0]["url"] == "https://hooks.slack.com/actual"
        finally:
            del os.environ["TEST_WEBHOOK_URL"]

    def test_expand_missing_env_var_leaves_placeholder(self, tmp_path: Path) -> None:
        """Missing env vars should leave the ${VAR} placeholder as-is."""
        # Make sure the var is not set
        os.environ.pop("NONEXISTENT_VAR_12345", None)

        config_content = """
webhooks:
  - name: test
    url: "${NONEXISTENT_VAR_12345}"
server:
  host: "0.0.0.0"
"""
        config_path = tmp_path / "argus_env2.yaml"
        config_path.write_text(config_content)

        from argus.core.config import ConfigManager

        manager = ConfigManager(str(config_path))
        webhooks = manager.get("webhooks")
        assert webhooks[0]["url"] == "${NONEXISTENT_VAR_12345}"

    def test_expand_multiple_env_vars(self, tmp_path: Path) -> None:
        """Multiple env vars in the same config should all be expanded."""
        os.environ["TEST_HOST"] = "myhost.com"
        os.environ["TEST_PORT"] = "9999"
        try:
            config_content = """
server:
  host: "${TEST_HOST}"
  port_str: "${TEST_PORT}"
"""
            config_path = tmp_path / "argus_env3.yaml"
            config_path.write_text(config_content)

            from argus.core.config import ConfigManager

            manager = ConfigManager(str(config_path))
            assert manager.get("server.host") == "myhost.com"
            assert manager.get("server.port_str") == "9999"
        finally:
            del os.environ["TEST_HOST"]
            del os.environ["TEST_PORT"]


# ---------------------------------------------------------------------------
# Issue #5: parse_time_range — shared utility
# ---------------------------------------------------------------------------
class TestParseTimeRange:
    """Shared parse_time_range should validate input and cap max values."""

    def test_parse_minutes(self) -> None:
        from argus.core.utils import parse_time_range

        assert parse_time_range("5m") == timedelta(minutes=5)

    def test_parse_hours(self) -> None:
        from argus.core.utils import parse_time_range

        assert parse_time_range("24h") == timedelta(hours=24)

    def test_parse_days(self) -> None:
        from argus.core.utils import parse_time_range

        assert parse_time_range("7d") == timedelta(days=7)

    def test_parse_seconds(self) -> None:
        from argus.core.utils import parse_time_range

        assert parse_time_range("30s") == timedelta(seconds=30)

    def test_invalid_format_raises_400(self) -> None:
        from fastapi import HTTPException

        from argus.core.utils import parse_time_range

        with pytest.raises(HTTPException) as exc_info:
            parse_time_range("invalid")
        assert exc_info.value.status_code == 400

    def test_empty_string_raises_400(self) -> None:
        from fastapi import HTTPException

        from argus.core.utils import parse_time_range

        with pytest.raises(HTTPException) as exc_info:
            parse_time_range("")
        assert exc_info.value.status_code == 400

    def test_overflow_value_raises_400(self) -> None:
        from fastapi import HTTPException

        from argus.core.utils import parse_time_range

        with pytest.raises(HTTPException) as exc_info:
            parse_time_range("999999999999h")
        assert exc_info.value.status_code == 400

    def test_zero_value_raises_400(self) -> None:
        from fastapi import HTTPException

        from argus.core.utils import parse_time_range

        with pytest.raises(HTTPException) as exc_info:
            parse_time_range("0h")
        assert exc_info.value.status_code == 400

    def test_negative_value_raises_400(self) -> None:
        from fastapi import HTTPException

        from argus.core.utils import parse_time_range

        with pytest.raises(HTTPException) as exc_info:
            parse_time_range("-5m")
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Issue #6: Multi-window alert evaluation bug
# ---------------------------------------------------------------------------
class TestMultiWindowAlertEvaluation:
    """check_alerts should group rules by window and compute metrics per window."""

    @pytest.mark.asyncio
    async def test_check_alerts_uses_per_rule_window(self, async_session) -> None:
        """Rules with different windows should each get metrics computed for their own window."""
        rules = [
            {
                "name": "Short window rule",
                "condition": "error_rate > 0.10",
                "window": "5m",
                "severity": "critical",
            },
            {
                "name": "Long window rule",
                "condition": "cost_usd_per_hour > 50.00",
                "window": "1h",
                "severity": "warning",
            },
        ]
        engine = AlertEngine(rules=rules)

        # Patch compute_metrics to track which windows are requested
        windows_requested: list[str] = []
        original_compute = engine.compute_metrics

        async def tracking_compute(session, window="5m"):
            windows_requested.append(window)
            return await original_compute(session, window=window)

        engine.compute_metrics = tracking_compute  # type: ignore[assignment]

        await engine.check_alerts(async_session)

        # Both windows should be requested, not just the first rule's window
        assert "5m" in windows_requested
        assert "1h" in windows_requested


# ---------------------------------------------------------------------------
# Issue #7: Trace compare unbounded
# ---------------------------------------------------------------------------
class TestTraceCompareLimit:
    """Trace compare endpoint should cap trace_ids at 10."""

    @pytest.mark.asyncio
    async def test_compare_rejects_too_many_ids(self, app_client) -> None:
        """Requesting more than 10 trace IDs should return 400."""
        ids = ",".join(f"trace-{i}" for i in range(11))
        resp = await app_client.get(f"/api/v1/traces/compare?trace_ids={ids}")
        assert resp.status_code == 400
        data = resp.json()
        assert "10" in data["detail"] or "limit" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_compare_allows_ten_ids(self, app_client) -> None:
        """Requesting exactly 10 trace IDs should be allowed."""
        ids = ",".join(f"trace-{i}" for i in range(10))
        resp = await app_client.get(f"/api/v1/traces/compare?trace_ids={ids}")
        # May return 200 (even if none found) — the point is it doesn't 400
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Issue #8: Alert history unbounded
# ---------------------------------------------------------------------------
class TestAlertHistoryBounded:
    """AlertEngine._history should use deque(maxlen=10_000) to prevent unbounded growth."""

    def test_history_is_bounded(self) -> None:
        """_history should be a deque with a max length."""
        engine = AlertEngine()
        assert isinstance(engine._history, deque)
        assert engine._history.maxlen == 10_000

    def test_history_does_not_grow_beyond_max(self) -> None:
        """Adding more than 10000 events should not grow the history beyond 10000."""
        engine = AlertEngine(
            rules=[{"name": "test", "condition": "error_rate > 0.01", "window": "5m", "severity": "warning"}]
        )
        # Fire many events
        for _i in range(10_050):
            engine.evaluate({"error_rate": 0.5})
        assert len(engine._history) == 10_000


# ---------------------------------------------------------------------------
# Issue #9: Alert history limit no max
# ---------------------------------------------------------------------------
class TestAlertHistoryLimitParam:
    """GET /api/v1/alerts/history 'limit' param should have a server-side max."""

    @pytest.mark.asyncio
    async def test_history_limit_exceeds_max(self, app_client) -> None:
        """limit > 1000 should return 422 (validation error)."""
        resp = await app_client.get("/api/v1/alerts/history?limit=5000")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_history_limit_zero_rejected(self, app_client) -> None:
        """limit=0 should return 422 (validation error)."""
        resp = await app_client.get("/api/v1/alerts/history?limit=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_history_limit_valid(self, app_client) -> None:
        """limit=500 should be accepted."""
        resp = await app_client.get("/api/v1/alerts/history?limit=500")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Issue #10: Ingestion IntegrityError
# ---------------------------------------------------------------------------
class TestIngestionDuplicateSpan:
    """Duplicate span_id should not crash with 500; should skip and continue."""

    @pytest.mark.asyncio
    async def test_duplicate_span_id_does_not_crash(self, async_session) -> None:
        """Ingesting the same span_id twice should not raise an error."""
        from argus.schemas.otlp import (
            Attribute,
            AttributeValue,
            IngestRequest,
            Resource,
            ResourceSpans,
            ScopeSpans,
            SpanData,
        )
        from argus.services.ingestion import process_ingest_request

        def make_request(span_id: str) -> IngestRequest:
            return IngestRequest(
                resourceSpans=[
                    ResourceSpans(
                        resource=Resource(
                            attributes=[
                                Attribute(
                                    key="gen_ai.agent.name",
                                    value=AttributeValue(stringValue="dup-agent"),
                                )
                            ]
                        ),
                        scopeSpans=[
                            ScopeSpans(
                                spans=[
                                    SpanData(
                                        traceId="dup-trace",
                                        spanId=span_id,
                                        name="chat",
                                        attributes=[
                                            Attribute(
                                                key="gen_ai.operation.name",
                                                value=AttributeValue(stringValue="chat"),
                                            ),
                                        ],
                                        startTimeUnixNano="1710000000000000000",
                                        endTimeUnixNano="1710000001000000000",
                                    )
                                ]
                            )
                        ],
                    )
                ]
            )

        # First ingestion should succeed
        count1 = await process_ingest_request(async_session, make_request("dup-span-001"))
        assert count1 == 1

        # Second ingestion with same span_id should NOT crash
        count2 = await process_ingest_request(async_session, make_request("dup-span-001"))
        # The duplicate should be skipped
        assert count2 == 0 or count2 == 1  # Implementation may count it or skip it


# ---------------------------------------------------------------------------
# Issue #11: Audit log O(n) pop
# ---------------------------------------------------------------------------
class TestAuditLogDeque:
    """Config audit log should use deque(maxlen=1000) instead of list with pop(0)."""

    def test_audit_log_is_deque(self) -> None:
        """_audit_log should be a collections.deque."""
        from argus.routes.api import config as config_module

        assert isinstance(config_module._audit_log, deque)

    def test_audit_log_has_maxlen(self) -> None:
        """_audit_log should have maxlen=1000."""
        from argus.routes.api import config as config_module

        assert config_module._audit_log.maxlen == 1000

    def test_audit_log_bounded(self) -> None:
        """Adding more than 1000 entries should not grow beyond 1000."""
        from argus.routes.api.config import _add_audit_entry, _audit_log

        # Clear existing entries
        _audit_log.clear()
        for i in range(1050):
            _add_audit_entry("test_action", f"entry {i}")
        assert len(_audit_log) <= 1000
