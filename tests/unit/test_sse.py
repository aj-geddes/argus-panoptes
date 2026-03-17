"""Tests for SSE broadcaster — real-time dashboard updates."""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_broadcaster_subscribe_and_publish() -> None:
    """SSE broadcaster should deliver events to subscribers."""
    from argus.core.sse import SSEBroadcaster

    broadcaster = SSEBroadcaster()
    received: list[dict] = []

    async def collect_events():
        async for event in broadcaster.subscribe():
            received.append(event)
            if len(received) >= 2:
                break

    # Start a consumer
    task = asyncio.create_task(collect_events())

    # Give the subscriber time to register
    await asyncio.sleep(0.05)

    # Publish events
    await broadcaster.publish({"event": "metrics", "data": "update1"})
    await broadcaster.publish({"event": "metrics", "data": "update2"})

    await asyncio.wait_for(task, timeout=2.0)
    assert len(received) == 2
    assert received[0]["data"] == "update1"
    assert received[1]["data"] == "update2"


@pytest.mark.asyncio
async def test_broadcaster_multiple_subscribers() -> None:
    """SSE broadcaster should deliver events to all subscribers."""
    from argus.core.sse import SSEBroadcaster

    broadcaster = SSEBroadcaster()
    received_a: list[dict] = []
    received_b: list[dict] = []

    async def collect_a():
        async for event in broadcaster.subscribe():
            received_a.append(event)
            if len(received_a) >= 1:
                break

    async def collect_b():
        async for event in broadcaster.subscribe():
            received_b.append(event)
            if len(received_b) >= 1:
                break

    task_a = asyncio.create_task(collect_a())
    task_b = asyncio.create_task(collect_b())
    await asyncio.sleep(0.05)

    await broadcaster.publish({"event": "test", "data": "hello"})

    await asyncio.wait_for(task_a, timeout=2.0)
    await asyncio.wait_for(task_b, timeout=2.0)

    assert len(received_a) == 1
    assert len(received_b) == 1


@pytest.mark.asyncio
async def test_broadcaster_subscriber_count() -> None:
    """SSE broadcaster should track subscriber count."""
    from argus.core.sse import SSEBroadcaster

    broadcaster = SSEBroadcaster()
    assert broadcaster.subscriber_count == 0

    queue = broadcaster._add_subscriber()
    assert broadcaster.subscriber_count == 1

    broadcaster._remove_subscriber(queue)
    assert broadcaster.subscriber_count == 0


@pytest.mark.asyncio
async def test_broadcaster_publish_no_subscribers() -> None:
    """SSE broadcaster publish should not raise when there are no subscribers."""
    from argus.core.sse import SSEBroadcaster

    broadcaster = SSEBroadcaster()
    # Should not raise
    await broadcaster.publish({"event": "test", "data": "nobody listening"})


@pytest.mark.asyncio
async def test_sse_endpoint_registered() -> None:
    """The SSE dashboard route should be registered on the app."""
    from argus.routes.api.sse import router

    route_paths = [r.path for r in router.routes]
    # Router has prefix /sse, so individual route is /dashboard
    assert any("dashboard" in p for p in route_paths)
