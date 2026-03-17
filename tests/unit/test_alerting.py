"""Tests for the alert rule engine."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from argus.services.alerting import (
    AlertEngine,
    AlertEvent,
    AlertRule,
    ConditionEvaluator,
    parse_condition,
)


class TestParseCondition:
    """Test condition string parsing."""

    def test_parse_simple_gt(self) -> None:
        metric, op, threshold = parse_condition("error_rate > 0.10")
        assert metric == "error_rate"
        assert op == ">"
        assert threshold == 0.10

    def test_parse_gte(self) -> None:
        metric, op, threshold = parse_condition("cost_usd_per_hour >= 50.00")
        assert metric == "cost_usd_per_hour"
        assert op == ">="
        assert threshold == 50.00

    def test_parse_lt(self) -> None:
        metric, op, threshold = parse_condition("success_rate < 0.90")
        assert metric == "success_rate"
        assert op == "<"
        assert threshold == 0.90

    def test_parse_lte(self) -> None:
        metric, op, threshold = parse_condition("avg_latency_ms <= 1000")
        assert metric == "avg_latency_ms"
        assert op == "<="
        assert threshold == 1000.0

    def test_parse_eq(self) -> None:
        metric, op, threshold = parse_condition("total_errors == 5")
        assert metric == "total_errors"
        assert op == "=="
        assert threshold == 5.0

    def test_parse_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid condition"):
            parse_condition("invalid condition format")

    def test_parse_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid condition"):
            parse_condition("")


class TestConditionEvaluator:
    """Test condition evaluation against metric snapshots."""

    def test_gt_true(self) -> None:
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("error_rate", ">", 0.10, {"error_rate": 0.15})
        assert result is True

    def test_gt_false(self) -> None:
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("error_rate", ">", 0.10, {"error_rate": 0.05})
        assert result is False

    def test_gte_equal(self) -> None:
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("error_rate", ">=", 0.10, {"error_rate": 0.10})
        assert result is True

    def test_lt_true(self) -> None:
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("success_rate", "<", 0.90, {"success_rate": 0.85})
        assert result is True

    def test_lte_equal(self) -> None:
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("count", "<=", 100.0, {"count": 100.0})
        assert result is True

    def test_eq_true(self) -> None:
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("total", "==", 5.0, {"total": 5.0})
        assert result is True

    def test_missing_metric_returns_false(self) -> None:
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("nonexistent", ">", 0.10, {"error_rate": 0.15})
        assert result is False

    def test_unknown_operator_returns_false(self) -> None:
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("error_rate", "!=", 0.10, {"error_rate": 0.15})
        assert result is False


class TestAlertRule:
    """Test AlertRule data class."""

    def test_create_alert_rule(self) -> None:
        rule = AlertRule(
            name="High error rate",
            condition="error_rate > 0.10",
            window="5m",
            severity="critical",
            notify=["webhook"],
        )
        assert rule.name == "High error rate"
        assert rule.condition == "error_rate > 0.10"
        assert rule.window == "5m"
        assert rule.severity == "critical"
        assert rule.notify == ["webhook"]


class TestAlertEvent:
    """Test AlertEvent data class."""

    def test_create_alert_event(self) -> None:
        event = AlertEvent(
            rule_name="High error rate",
            severity="critical",
            status="fired",
            metric_value=0.15,
            threshold=0.10,
            message="error_rate is 0.15, threshold > 0.10",
        )
        assert event.rule_name == "High error rate"
        assert event.status == "fired"
        assert event.metric_value == 0.15
        assert event.threshold == 0.10
        assert event.fired_at is not None


class TestAlertEngine:
    """Test the AlertEngine service."""

    def _make_engine(self, rules: list[dict[str, Any]] | None = None) -> AlertEngine:
        """Create an AlertEngine with test rules."""
        if rules is None:
            rules = [
                {
                    "name": "High error rate",
                    "condition": "error_rate > 0.10",
                    "window": "5m",
                    "severity": "critical",
                    "notify": ["webhook"],
                },
                {
                    "name": "Cost spike",
                    "condition": "cost_usd_per_hour > 50.00",
                    "window": "1h",
                    "severity": "warning",
                    "notify": ["webhook"],
                },
            ]
        return AlertEngine(rules=rules)

    def test_load_rules(self) -> None:
        engine = self._make_engine()
        assert len(engine.rules) == 2
        assert engine.rules[0].name == "High error rate"
        assert engine.rules[1].name == "Cost spike"

    def test_load_empty_rules(self) -> None:
        engine = self._make_engine(rules=[])
        assert len(engine.rules) == 0

    def test_evaluate_fires_alert(self) -> None:
        engine = self._make_engine()
        metrics = {"error_rate": 0.15, "cost_usd_per_hour": 10.0}
        events = engine.evaluate(metrics)
        assert len(events) == 1
        assert events[0].rule_name == "High error rate"
        assert events[0].status == "fired"

    def test_evaluate_fires_multiple_alerts(self) -> None:
        engine = self._make_engine()
        metrics = {"error_rate": 0.20, "cost_usd_per_hour": 75.0}
        events = engine.evaluate(metrics)
        assert len(events) == 2

    def test_evaluate_no_alerts(self) -> None:
        engine = self._make_engine()
        metrics = {"error_rate": 0.05, "cost_usd_per_hour": 10.0}
        events = engine.evaluate(metrics)
        assert len(events) == 0

    def test_update_rules(self) -> None:
        engine = self._make_engine()
        new_rules = [
            {
                "name": "Latency spike",
                "condition": "avg_latency_ms > 5000",
                "window": "10m",
                "severity": "warning",
                "notify": ["webhook"],
            },
        ]
        engine.update_rules(new_rules)
        assert len(engine.rules) == 1
        assert engine.rules[0].name == "Latency spike"

    def test_get_alert_history(self) -> None:
        engine = self._make_engine()
        metrics = {"error_rate": 0.20}
        engine.evaluate(metrics)
        history = engine.get_history()
        assert len(history) == 1
        assert history[0].rule_name == "High error rate"

    def test_get_alert_history_limit(self) -> None:
        engine = self._make_engine()
        for _ in range(5):
            engine.evaluate({"error_rate": 0.20})
        history = engine.get_history(limit=3)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_compute_metrics_from_db(self, async_session: AsyncSession) -> None:
        """Test computing metrics from the database for alert evaluation."""
        engine = self._make_engine()
        metrics = await engine.compute_metrics(async_session, window="5m")
        assert "error_rate" in metrics
        assert "cost_usd_per_hour" in metrics
        assert "avg_latency_ms" in metrics
        assert "total_traces" in metrics

    @pytest.mark.asyncio
    async def test_check_alerts_integration(self, async_session: AsyncSession) -> None:
        """Test full check_alerts cycle (compute + evaluate)."""
        engine = self._make_engine()
        events = await engine.check_alerts(async_session)
        # With no data, no alerts should fire
        assert len(events) == 0
