"""Tests for the webhook notification service."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from argus.services.alerting import AlertEvent
from argus.services.webhooks import WebhookConfig, WebhookNotifier


class TestWebhookConfig:
    """Test WebhookConfig data class."""

    def test_create_config(self) -> None:
        config = WebhookConfig(
            name="slack-alerts",
            url="https://hooks.slack.com/test",
            events=["alert.fired", "alert.resolved"],
        )
        assert config.name == "slack-alerts"
        assert config.url == "https://hooks.slack.com/test"
        assert config.events == ["alert.fired", "alert.resolved"]

    def test_create_config_defaults(self) -> None:
        config = WebhookConfig(
            name="test",
            url="https://example.com/webhook",
        )
        assert config.events == []


class TestWebhookNotifier:
    """Test the WebhookNotifier service."""

    def _make_notifier(self, webhooks: list[dict[str, Any]] | None = None) -> WebhookNotifier:
        if webhooks is None:
            webhooks = [
                {
                    "name": "slack-alerts",
                    "url": "https://hooks.slack.com/test",
                    "events": ["alert.fired", "alert.resolved"],
                },
            ]
        return WebhookNotifier(webhooks=webhooks)

    def test_load_webhooks(self) -> None:
        notifier = self._make_notifier()
        assert len(notifier.configs) == 1
        assert notifier.configs[0].name == "slack-alerts"

    def test_load_empty_webhooks(self) -> None:
        notifier = self._make_notifier(webhooks=[])
        assert len(notifier.configs) == 0

    def test_update_configs(self) -> None:
        notifier = self._make_notifier()
        new_webhooks = [
            {
                "name": "pagerduty",
                "url": "https://events.pagerduty.com/test",
                "events": ["alert.fired"],
            },
        ]
        notifier.update_configs(new_webhooks)
        assert len(notifier.configs) == 1
        assert notifier.configs[0].name == "pagerduty"

    @pytest.mark.asyncio
    async def test_send_alert_fired(self) -> None:
        notifier = self._make_notifier()
        event = AlertEvent(
            rule_name="High error rate",
            severity="critical",
            status="fired",
            metric_value=0.15,
            threshold=0.10,
            message="error_rate is 0.15, threshold > 0.10",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("argus.services.webhooks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await notifier.send_alert(event)
            assert len(results) == 1
            assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_send_alert_no_matching_webhooks(self) -> None:
        notifier = self._make_notifier(
            webhooks=[
                {
                    "name": "slack",
                    "url": "https://hooks.slack.com/test",
                    "events": ["alert.resolved"],  # Only resolved, not fired
                },
            ]
        )
        event = AlertEvent(
            rule_name="Test",
            severity="warning",
            status="fired",
            metric_value=0.15,
            threshold=0.10,
            message="test",
        )
        results = await notifier.send_alert(event)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_send_alert_handles_error(self) -> None:
        notifier = self._make_notifier()
        event = AlertEvent(
            rule_name="Test",
            severity="critical",
            status="fired",
            metric_value=0.15,
            threshold=0.10,
            message="test",
        )

        with patch("argus.services.webhooks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await notifier.send_alert(event)
            assert len(results) == 1
            assert results[0]["success"] is False
            assert "Connection refused" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_send_alert_empty_events_matches_all(self) -> None:
        """Webhook with no events filter should match all event types."""
        notifier = self._make_notifier(
            webhooks=[
                {
                    "name": "catch-all",
                    "url": "https://example.com/webhook",
                    "events": [],  # Empty = match all
                },
            ]
        )
        event = AlertEvent(
            rule_name="Test",
            severity="warning",
            status="fired",
            metric_value=0.15,
            threshold=0.10,
            message="test",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("argus.services.webhooks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await notifier.send_alert(event)
            assert len(results) == 1
            assert results[0]["success"] is True

    def test_build_payload(self) -> None:
        notifier = self._make_notifier()
        event = AlertEvent(
            rule_name="High error rate",
            severity="critical",
            status="fired",
            metric_value=0.15,
            threshold=0.10,
            message="error_rate is 0.15, threshold > 0.10",
        )
        payload = notifier.build_payload(event)
        assert payload["rule_name"] == "High error rate"
        assert payload["severity"] == "critical"
        assert payload["status"] == "fired"
        assert payload["metric_value"] == 0.15
        assert payload["threshold"] == 0.10
        assert "fired_at" in payload
