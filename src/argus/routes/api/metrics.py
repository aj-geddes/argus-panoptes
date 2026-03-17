"""Metrics API routes — aggregated metrics summary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from argus.core.database import get_session
from argus.services.metrics import MetricsService

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

_metrics = MetricsService()


@router.get("/summary")
async def metrics_summary(
    time_range: str = "1h",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get aggregated metrics summary across all agents."""
    now = datetime.now(UTC)
    delta = _parse_time_range(time_range)
    time_start = now - delta

    return await _metrics.get_summary(
        session=session,
        time_start=time_start,
        time_end=now,
    )


def _parse_time_range(time_range: str) -> timedelta:
    """Parse a time range string like '1h', '24h', '7d' into a timedelta."""
    unit = time_range[-1]
    value = int(time_range[:-1])
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    return timedelta(hours=1)
