"""Shared utility functions for Argus Panoptes."""

from __future__ import annotations

import re
from datetime import timedelta

from fastapi import HTTPException

# Match patterns like "5m", "24h", "7d", "30s"
_TIME_RANGE_RE = re.compile(r"^(\d+)([smhd])$")

# Maximum values per unit to prevent overflow
_MAX_VALUES = {
    "s": 86400 * 365,  # 1 year in seconds
    "m": 60 * 24 * 365,  # 1 year in minutes
    "h": 24 * 365,  # 1 year in hours
    "d": 365,  # 1 year in days
}


def parse_time_range(time_range: str) -> timedelta:
    """Parse a time range string like '1h', '24h', '7d' into a timedelta.

    Validates input with regex, caps maximum values to prevent overflow,
    and raises HTTP 400 on invalid input.

    Args:
        time_range: A string like '30s', '5m', '1h', '7d'.

    Returns:
        A timedelta representing the time range.

    Raises:
        HTTPException: 400 if the format is invalid or the value is out of range.
    """
    if not time_range or not isinstance(time_range, str):
        raise HTTPException(status_code=400, detail="Invalid time range: empty or non-string value")

    match = _TIME_RANGE_RE.match(time_range.strip())
    if not match:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time range format: '{time_range}'. Expected format like '5m', '1h', '7d'.",
        )

    value = int(match.group(1))
    unit = match.group(2)

    max_val = _MAX_VALUES[unit]
    if value <= 0 or value > max_val:
        raise HTTPException(
            status_code=400,
            detail=f"Time range value out of bounds: {value}{unit}. Must be between 1 and {max_val}{unit}.",
        )

    if unit == "s":
        return timedelta(seconds=value)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)

    # Should never reach here due to regex, but satisfy type checker
    raise HTTPException(status_code=400, detail=f"Unknown time unit: {unit}")  # pragma: no cover
