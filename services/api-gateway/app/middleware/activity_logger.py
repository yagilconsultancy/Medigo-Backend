"""Fire-and-forget emitter for admin activity-log entries.

The gateway is the one place that sees every admin mutation across all seven
services along with JWT-validated identity, so it is where activity logging
is cheapest to make complete. Entries are queued and drained by a background
task: logging must never add latency to, or fail, the request it describes.

Transport is auth-service's existing POST /internal/activity-logs. It is
deliberately behind `emit()` so it can be swapped for the RabbitMQ event bus
later without touching the proxy.
"""

import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_QUEUE_MAX_SIZE = 1000
_DRAIN_TIMEOUT_SECONDS = 5.0
_MAX_ATTEMPTS = 2

_queue: asyncio.Queue | None = None
_worker: asyncio.Task | None = None
_dropped = 0


async def start_activity_logger() -> None:
    global _queue, _worker
    if _worker is not None:
        return
    _queue = asyncio.Queue(maxsize=_QUEUE_MAX_SIZE)
    _worker = asyncio.create_task(_drain())
    logger.info("Activity logger started")


async def stop_activity_logger() -> None:
    global _queue, _worker
    if _worker is None:
        return
    _worker.cancel()
    try:
        await _worker
    except asyncio.CancelledError:
        pass
    finally:
        _worker = None
        _queue = None
        logger.info("Activity logger stopped (dropped=%d)", _dropped)


def emit(entry: dict) -> None:
    """Queue an entry. Never blocks, never raises."""
    global _dropped
    if _queue is None:
        return
    try:
        _queue.put_nowait(entry)
    except asyncio.QueueFull:
        _dropped += 1
        # Log sparsely: a full queue means auth-service is struggling, and a
        # per-entry warning would amplify the problem.
        if _dropped % 100 == 1:
            logger.warning(
                "Activity log queue full, dropping entries (total dropped=%d)",
                _dropped,
            )


async def _drain() -> None:
    assert _queue is not None
    url = f"{settings.AUTH_SERVICE_URL}/internal/activity-logs"
    headers = {"X-Internal-Service": "api-gateway"}

    async with httpx.AsyncClient(timeout=_DRAIN_TIMEOUT_SECONDS) as client:
        while True:
            entry = await _queue.get()
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                try:
                    response = await client.post(url, json=entry, headers=headers)
                    if response.status_code < 500:
                        # 4xx is our bug, not a transient fault -- do not retry.
                        if response.status_code >= 400:
                            logger.warning(
                                "Activity log rejected (%s): %s",
                                response.status_code,
                                response.text[:200],
                            )
                        break
                except (httpx.RequestError, asyncio.TimeoutError) as exc:
                    if attempt == _MAX_ATTEMPTS:
                        logger.warning("Activity log emit failed: %s", exc)
                if attempt < _MAX_ATTEMPTS:
                    await asyncio.sleep(0.5)
            _queue.task_done()
