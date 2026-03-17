"""SSE endpoint for real-time dashboard updates."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from argus.core.sse import dashboard_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["sse"])


@router.get("/dashboard")
async def sse_dashboard():
    """SSE endpoint for live dashboard updates.

    Clients connect here and receive real-time metric update events.
    """

    async def event_generator():
        async for event in dashboard_broadcaster.subscribe():
            event_type = event.get("event", "message")
            data = event.get("data", "")
            if isinstance(data, dict):
                data = json.dumps(data)
            yield {"event": event_type, "data": data}

    return EventSourceResponse(event_generator())
