"""Alert management API routes — CRUD for alert rules and history."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from argus.core.database import get_session
from argus.services.alerting import AlertEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

# Module-level alert engine, initialized from config
_alert_engine: AlertEngine | None = None


def get_alert_engine() -> AlertEngine:
    """Get or create the alert engine singleton."""
    global _alert_engine
    if _alert_engine is None:
        _alert_engine = AlertEngine()
    return _alert_engine


def init_alert_engine(rules: list[dict[str, Any]]) -> None:
    """Initialize the alert engine with rules from config."""
    global _alert_engine
    _alert_engine = AlertEngine(rules=rules)
    logger.info("Alert engine initialized with %d rules", len(_alert_engine.rules))


@router.get("/rules")
async def list_alert_rules() -> dict[str, Any]:
    """List all configured alert rules."""
    engine = get_alert_engine()
    return {
        "rules": [
            {
                "name": r.name,
                "condition": r.condition,
                "window": r.window,
                "severity": r.severity,
                "notify": r.notify,
            }
            for r in engine.rules
        ],
        "total": len(engine.rules),
    }


@router.get("/history")
async def get_alert_history(limit: int = Query(default=100, ge=1, le=1000)) -> dict[str, Any]:
    """Get recent alert event history."""
    engine = get_alert_engine()
    history = engine.get_history(limit=limit)
    return {
        "events": [
            {
                "rule_name": e.rule_name,
                "severity": e.severity,
                "status": e.status,
                "metric_value": e.metric_value,
                "threshold": e.threshold,
                "message": e.message,
                "fired_at": e.fired_at.isoformat(),
            }
            for e in history
        ],
        "total": len(history),
    }


@router.post("/check")
async def check_alerts(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Manually trigger an alert check against current metrics."""
    engine = get_alert_engine()
    metrics = await engine.compute_metrics(session)
    events = engine.evaluate(metrics)
    return {
        "events": [
            {
                "rule_name": e.rule_name,
                "severity": e.severity,
                "status": e.status,
                "metric_value": e.metric_value,
                "threshold": e.threshold,
                "message": e.message,
                "fired_at": e.fired_at.isoformat(),
            }
            for e in events
        ],
        "metrics": {k: round(v, 6) for k, v in metrics.items()},
    }
