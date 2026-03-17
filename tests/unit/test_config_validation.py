"""Tests for config validation with clear error messages."""

from __future__ import annotations

import yaml

from argus.schemas.config import (
    AlertRuleConfig,
    AlertsConfig,
    DashboardConfig,
    WebhookConfigSchema,
    validate_config_yaml,
)


class TestConfigValidation:
    """Test config validation functions."""

    def test_validate_valid_full_config(self) -> None:
        config_yaml = yaml.dump(
            {
                "server": {"host": "0.0.0.0", "port": 8000, "workers": 4, "log_level": "INFO"},
                "database": {"url": "sqlite+aiosqlite:///./argus.db", "pool_size": 10},
                "ingestion": {"otlp_enabled": True, "rest_enabled": True},
                "metrics": {"aggregation_windows": ["1m", "5m"], "retention_days": 90},
                "alerts": {
                    "enabled": True,
                    "check_interval_seconds": 30,
                    "rules": [
                        {
                            "name": "Test",
                            "condition": "error_rate > 0.10",
                            "window": "5m",
                            "severity": "critical",
                            "notify": ["webhook"],
                        },
                    ],
                },
                "dashboard": {"refresh_interval_seconds": 5, "default_time_range": "1h"},
            }
        )
        is_valid, errors = validate_config_yaml(config_yaml)
        assert is_valid is True
        assert errors == []

    def test_validate_minimal_config(self) -> None:
        config_yaml = yaml.dump({})
        is_valid, _errors = validate_config_yaml(config_yaml)
        assert is_valid is True  # All fields have defaults

    def test_validate_invalid_yaml_syntax(self) -> None:
        is_valid, errors = validate_config_yaml("{ invalid: [yaml")
        assert is_valid is False
        assert len(errors) > 0
        assert "YAML" in errors[0] or "yaml" in errors[0]

    def test_validate_invalid_port(self) -> None:
        config_yaml = yaml.dump({"server": {"port": "not-a-number"}})
        is_valid, errors = validate_config_yaml(config_yaml)
        assert is_valid is False
        assert len(errors) > 0

    def test_validate_invalid_alert_rule(self) -> None:
        config_yaml = yaml.dump(
            {
                "alerts": {
                    "enabled": True,
                    "rules": [
                        {
                            "name": "Bad rule",
                            # Missing required fields
                        },
                    ],
                },
            }
        )
        is_valid, _errors = validate_config_yaml(config_yaml)
        assert is_valid is False

    def test_validate_non_dict_returns_error(self) -> None:
        is_valid, errors = validate_config_yaml("just a string")
        assert is_valid is False
        assert any("dictionary" in e.lower() or "dict" in e.lower() or "object" in e.lower() for e in errors)


class TestAlertRuleConfig:
    """Test alert rule config validation."""

    def test_valid_rule(self) -> None:
        rule = AlertRuleConfig(
            name="Test rule",
            condition="error_rate > 0.10",
            window="5m",
            severity="critical",
            notify=["webhook"],
        )
        assert rule.name == "Test rule"

    def test_defaults(self) -> None:
        rule = AlertRuleConfig(
            name="Test",
            condition="error_rate > 0.10",
        )
        assert rule.window == "5m"
        assert rule.severity == "warning"
        assert rule.notify == []


class TestWebhookConfigSchema:
    """Test webhook config schema validation."""

    def test_valid_webhook(self) -> None:
        wh = WebhookConfigSchema(
            name="slack",
            url="https://hooks.slack.com/test",
            events=["alert.fired"],
        )
        assert wh.name == "slack"
        assert wh.url == "https://hooks.slack.com/test"

    def test_defaults(self) -> None:
        wh = WebhookConfigSchema(
            name="test",
            url="https://example.com",
        )
        assert wh.events == []


class TestAlertsConfig:
    """Test alerts section config."""

    def test_defaults(self) -> None:
        config = AlertsConfig()
        assert config.enabled is False
        assert config.check_interval_seconds == 30
        assert config.rules == []


class TestDashboardConfig:
    """Test dashboard section config."""

    def test_defaults(self) -> None:
        config = DashboardConfig()
        assert config.refresh_interval_seconds == 5
        assert config.default_time_range == "1h"
