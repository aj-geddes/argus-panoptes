"""Pydantic schemas for config validation with clear error messages."""

from __future__ import annotations

import logging
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ServerConfig(BaseModel):
    """Server configuration section."""

    host: str = "0.0.0.0"  # nosec B104 — intentional for container deployment
    port: int = 8000
    workers: int = 4
    log_level: str = "INFO"


class DatabaseConfig(BaseModel):
    """Database configuration section."""

    url: str = "sqlite+aiosqlite:///./argus.db"
    pool_size: int = 10


class IngestionConfig(BaseModel):
    """Ingestion layer configuration."""

    otlp_enabled: bool = True
    otlp_port: int = 4318
    rest_enabled: bool = True
    max_batch_size: int = 1000
    flush_interval_seconds: int = 5


class MetricsConfig(BaseModel):
    """Metrics aggregation configuration."""

    aggregation_windows: list[str] = ["1m", "5m", "1h", "1d"]
    retention_days: int = 90
    snapshot_interval_seconds: int = 60


class AlertRuleConfig(BaseModel):
    """A single alert rule configuration."""

    name: str
    condition: str
    window: str = "5m"
    severity: str = "warning"
    notify: list[str] = []


class AlertsConfig(BaseModel):
    """Alerts section configuration."""

    enabled: bool = False
    check_interval_seconds: int = 30
    rules: list[AlertRuleConfig] = []


class WebhookConfigSchema(BaseModel):
    """Webhook configuration schema."""

    name: str
    url: str
    events: list[str] = []


class DashboardConfig(BaseModel):
    """Dashboard configuration section."""

    refresh_interval_seconds: int = 5
    default_time_range: str = "1h"
    charts: list[dict[str, Any]] = []


class ArgusConfig(BaseModel):
    """Top-level Argus configuration — validates the entire config file."""

    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    ingestion: IngestionConfig = IngestionConfig()
    metrics: MetricsConfig = MetricsConfig()
    alerts: AlertsConfig = AlertsConfig()
    webhooks: list[WebhookConfigSchema] = []
    dashboard: DashboardConfig = DashboardConfig()


def validate_config_yaml(yaml_content: str) -> tuple[bool, list[str]]:
    """Validate a YAML config string against the ArgusConfig schema.

    Returns (is_valid, list_of_error_messages).
    """
    errors: list[str] = []

    # Step 1: Parse YAML
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return False, [f"YAML syntax error: {e}"]

    # Step 2: Ensure it's a dict
    if not isinstance(data, dict):
        return False, ["Config must be a YAML dictionary/object, not a scalar or list."]

    # Step 3: Validate against schema
    try:
        ArgusConfig(**data)
    except ValidationError as e:
        for err in e.errors():
            loc = " -> ".join(str(part) for part in err["loc"])
            msg = err["msg"]
            errors.append(f"{loc}: {msg}")
        return False, errors

    return True, []
