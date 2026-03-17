"""Metrics API routes — aggregated metrics summary."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from argus.core.database import get_session
from argus.core.utils import parse_time_range
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
    delta = parse_time_range(time_range)
    time_start = now - delta

    return await _metrics.get_summary(
        session=session,
        time_start=time_start,
        time_end=now,
    )
