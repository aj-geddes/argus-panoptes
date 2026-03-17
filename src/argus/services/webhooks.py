"""Webhook notification service — sends alert events to configured endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from argus.services.alerting import AlertEvent

logger = logging.getLogger(__name__)


@dataclass
class WebhookConfig:
    """Configuration for a single webhook endpoint."""

    name: str
    url: str
    events: list[str] = field(default_factory=list)


class WebhookNotifier:
    """Sends alert notifications to configured webhook endpoints via httpx async POST."""

    def __init__(self, webhooks: list[dict[str, Any]] | None = None) -> None:
        self.configs: list[WebhookConfig] = []
        if webhooks:
            self._load_configs(webhooks)

    def _load_configs(self, webhooks: list[dict[str, Any]]) -> None:
        """Load webhook configurations from config dicts."""
        self.configs = []
        for wh in webhooks:
            config = WebhookConfig(
                name=wh.get("name", "unnamed"),
                url=wh.get("url", ""),
                events=wh.get("events", []),
            )
            if config.url:
                self.configs.append(config)
            else:
                logger.warning("Skipping webhook '%s': no URL configured", config.name)

    def update_configs(self, webhooks: list[dict[str, Any]]) -> None:
        """Update webhook configs from new config (hot-reload support)."""
        self._load_configs(webhooks)
        logger.info("Webhook configs updated: %d webhooks loaded", len(self.configs))

    def build_payload(self, event: AlertEvent) -> dict[str, Any]:
        """Build the JSON payload for a webhook notification."""
        return {
            "rule_name": event.rule_name,
            "severity": event.severity,
            "status": event.status,
            "metric_value": event.metric_value,
            "threshold": event.threshold,
            "message": event.message,
            "fired_at": event.fired_at.isoformat(),
        }

    async def send_alert(self, event: AlertEvent) -> list[dict[str, Any]]:
        """Send an alert event to all matching webhook endpoints.

        Returns a list of result dicts with 'webhook', 'success', and optionally 'error'.
        """
        event_type = f"alert.{event.status}"
        results: list[dict[str, Any]] = []

        matching_configs = [c for c in self.configs if not c.events or event_type in c.events]

        if not matching_configs:
            return results

        payload = self.build_payload(event)

        async with httpx.AsyncClient(timeout=10.0) as client:
            for config in matching_configs:
                result: dict[str, Any] = {"webhook": config.name, "success": False}
                try:
                    response = await client.post(
                        config.url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    response.raise_for_status()
                    result["success"] = True
                    logger.info("Webhook '%s' sent successfully for '%s'", config.name, event.rule_name)
                except Exception as e:
                    result["error"] = str(e)
                    logger.warning(
                        "Webhook '%s' failed for '%s': %s",
                        config.name,
                        event.rule_name,
                        e,
                    )
                results.append(result)

        return results
