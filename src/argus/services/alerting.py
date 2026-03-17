"""Alert rule engine — evaluates conditions against metric snapshots."""

from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from argus.models.span import Span
from argus.models.trace import Trace

logger = logging.getLogger(__name__)

# Regex for parsing condition strings like "error_rate > 0.10"
_CONDITION_RE = re.compile(r"^\s*(\w+)\s*(>=|<=|==|>|<)\s*([\d.]+)\s*$")


def parse_condition(condition: str) -> tuple[str, str, float]:
    """Parse a condition string like 'error_rate > 0.10'.

    Returns (metric_name, operator, threshold).
    Raises ValueError if the condition is invalid.
    """
    match = _CONDITION_RE.match(condition)
    if not match:
        raise ValueError(f"Invalid condition: '{condition}'. Expected format: 'metric_name operator threshold'")
    metric = match.group(1)
    op = match.group(2)
    threshold = float(match.group(3))
    return metric, op, threshold


@dataclass
class AlertRule:
    """A single alert rule parsed from config."""

    name: str
    condition: str
    window: str = "5m"
    severity: str = "warning"
    notify: list[str] = field(default_factory=list)


@dataclass
class AlertEvent:
    """An alert event — fired when a condition is met."""

    rule_name: str
    severity: str
    status: str  # "fired" or "resolved"
    metric_value: float
    threshold: float
    message: str
    fired_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ConditionEvaluator:
    """Evaluates a parsed condition against a metrics dict."""

    def evaluate(self, metric: str, op: str, threshold: float, metrics: dict[str, float]) -> bool:
        """Evaluate a single condition against current metrics.

        Returns False if the metric is missing or the operator is unknown.
        """
        value = metrics.get(metric)
        if value is None:
            return False

        if op == ">":
            return value > threshold
        if op == ">=":
            return value >= threshold
        if op == "<":
            return value < threshold
        if op == "<=":
            return value <= threshold
        if op == "==":
            return value == threshold
        return False


class AlertEngine:
    """Manages alert rules, evaluates conditions, and tracks alert history."""

    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        self.rules: list[AlertRule] = []
        self._history: deque[AlertEvent] = deque(maxlen=10_000)
        self._evaluator = ConditionEvaluator()
        if rules:
            self._load_rules(rules)

    def _load_rules(self, rules: list[dict[str, Any]]) -> None:
        """Load alert rules from config dicts."""
        self.rules = []
        for r in rules:
            try:
                rule = AlertRule(
                    name=r["name"],
                    condition=r["condition"],
                    window=r.get("window", "5m"),
                    severity=r.get("severity", "warning"),
                    notify=r.get("notify", []),
                )
                # Validate the condition parses correctly
                parse_condition(rule.condition)
                self.rules.append(rule)
            except (KeyError, ValueError) as e:
                logger.warning("Skipping invalid alert rule: %s", e)

    def update_rules(self, rules: list[dict[str, Any]]) -> None:
        """Update rules from new config (hot-reload support)."""
        self._load_rules(rules)
        logger.info("Alert rules updated: %d rules loaded", len(self.rules))

    def evaluate(self, metrics: dict[str, float]) -> list[AlertEvent]:
        """Evaluate all rules against the given metrics.

        Returns a list of AlertEvents for rules that fired.
        """
        events: list[AlertEvent] = []
        for rule in self.rules:
            try:
                metric, op, threshold = parse_condition(rule.condition)
                if self._evaluator.evaluate(metric, op, threshold, metrics):
                    metric_value = metrics.get(metric, 0.0)
                    event = AlertEvent(
                        rule_name=rule.name,
                        severity=rule.severity,
                        status="fired",
                        metric_value=metric_value,
                        threshold=threshold,
                        message=f"{metric} is {metric_value}, threshold {op} {threshold}",
                    )
                    events.append(event)
                    self._history.append(event)
            except ValueError:
                logger.warning("Could not evaluate rule '%s': invalid condition", rule.name)
        return events

    def get_history(self, limit: int = 100) -> list[AlertEvent]:
        """Get recent alert history, newest first."""
        return sorted(self._history, key=lambda e: e.fired_at, reverse=True)[:limit]

    async def compute_metrics(
        self,
        session: AsyncSession,
        window: str = "5m",
    ) -> dict[str, float]:
        """Compute current metrics from the database for alert evaluation.

        Returns a dict of metric names to their current values.
        """
        now = datetime.now(UTC)
        delta = _parse_window(window)
        time_start = now - delta

        # Total spans in window
        span_count_q = select(func.count()).select_from(Span).where(Span.started_at >= time_start)
        result = await session.execute(span_count_q)
        total_spans = result.scalar() or 0

        # Error count
        error_q = select(func.count()).select_from(Span).where(Span.started_at >= time_start, Span.status == "error")
        result = await session.execute(error_q)
        error_count = result.scalar() or 0

        # Error rate
        error_rate = error_count / total_spans if total_spans > 0 else 0.0

        # Total cost in window
        cost_q = select(func.coalesce(func.sum(Span.cost_usd), 0.0)).where(Span.started_at >= time_start)
        result = await session.execute(cost_q)
        total_cost = float(result.scalar() or 0.0)

        # Cost per hour (extrapolate from window)
        window_hours = delta.total_seconds() / 3600.0
        cost_per_hour = total_cost / window_hours if window_hours > 0 else 0.0

        # Average latency
        latency_q = select(func.coalesce(func.avg(Span.latency_ms), 0.0)).where(
            Span.started_at >= time_start, Span.latency_ms > 0
        )
        result = await session.execute(latency_q)
        avg_latency = float(result.scalar() or 0.0)

        # Total traces
        trace_q = select(func.count()).select_from(Trace).where(Trace.started_at >= time_start)
        result = await session.execute(trace_q)
        total_traces = result.scalar() or 0

        return {
            "error_rate": error_rate,
            "cost_usd_per_hour": cost_per_hour,
            "avg_latency_ms": avg_latency,
            "total_spans": float(total_spans),
            "total_traces": float(total_traces),
            "total_cost_usd": total_cost,
            "error_count": float(error_count),
        }

    async def check_alerts(self, session: AsyncSession) -> list[AlertEvent]:
        """Full alert check cycle: compute metrics then evaluate rules.

        Groups rules by window, computes metrics per window, and evaluates
        each rule against the metrics for its own window.
        """
        if not self.rules:
            return []

        # Group rules by window
        window_groups: dict[str, list[AlertRule]] = {}
        for rule in self.rules:
            window_groups.setdefault(rule.window, []).append(rule)

        all_events: list[AlertEvent] = []
        for window, rules_in_window in window_groups.items():
            metrics = await self.compute_metrics(session, window=window)
            # Evaluate only the rules that belong to this window
            for rule in rules_in_window:
                try:
                    metric, op, threshold = parse_condition(rule.condition)
                    if self._evaluator.evaluate(metric, op, threshold, metrics):
                        metric_value = metrics.get(metric, 0.0)
                        event = AlertEvent(
                            rule_name=rule.name,
                            severity=rule.severity,
                            status="fired",
                            metric_value=metric_value,
                            threshold=threshold,
                            message=f"{metric} is {metric_value}, threshold {op} {threshold}",
                        )
                        all_events.append(event)
                        self._history.append(event)
                except ValueError:
                    logger.warning("Could not evaluate rule '%s': invalid condition", rule.name)
        return all_events


def _parse_window(window: str) -> timedelta:
    """Parse a time window string like '5m', '1h', '1d' into a timedelta."""
    if not window:
        return timedelta(minutes=5)
    unit = window[-1]
    try:
        value = int(window[:-1])
    except ValueError:
        return timedelta(minutes=5)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    return timedelta(minutes=5)
