"""SSE (Server-Sent Events) broadcaster for real-time dashboard updates."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Manages SSE subscribers and broadcasts events to all connected clients."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    @property
    def subscriber_count(self) -> int:
        """Return the number of active subscribers."""
        return len(self._subscribers)

    def _add_subscriber(self) -> asyncio.Queue[dict[str, Any]]:
        """Add a new subscriber queue. Returns the queue."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.append(queue)
        logger.debug("SSE subscriber added (total: %d)", len(self._subscribers))
        return queue

    def _remove_subscriber(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove a subscriber queue."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)
        logger.debug("SSE subscriber removed (total: %d)", len(self._subscribers))

    async def publish(self, event: dict[str, Any]) -> None:
        """Broadcast an event to all subscribers."""
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("SSE subscriber queue full, dropping event")

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to the event stream. Yields events as they arrive."""
        queue = self._add_subscriber()
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self._remove_subscriber(queue)


# Module-level singleton broadcaster
dashboard_broadcaster = SSEBroadcaster()
