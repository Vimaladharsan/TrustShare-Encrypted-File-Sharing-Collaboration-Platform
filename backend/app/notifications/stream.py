"""Server-Sent Events: one long-lived HTTP response per open browser tab.

The browser reads it with fetch() and its normal Authorization header (no token in the URL, so
nothing sensitive ends up in logs or history). Events:

    event: ready         {"unread": n}            – right after connecting
    event: notification  {...notification...}     – a new notification (from Redis pub/sub)
    event: reauth        {}                       – access token expired / device signed out:
                                                    refresh the token and reconnect
    event: reconnect     {}                       – max stream age reached: reconnect
    : ping                                        – heartbeat, keeps proxies from closing it
"""

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.security import issued_at_ms
from app.services.session_service import SessionService


def sse(event: str, data: Any) -> str:
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n"


async def event_stream(
    request: Request | None,
    redis: Redis,
    channel: str,
    payload: dict[str, Any],
    ready: dict[str, Any],
    event_name: str = "notification",
) -> AsyncIterator[str]:
    settings = get_settings()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    started = last_beat = time.monotonic()
    sessions = SessionService(redis)
    try:
        yield sse("ready", ready)
        while True:
            if request is not None and await request.is_disconnected():
                return
            if time.time() >= payload["exp"]:
                yield sse("reauth", {})
                return
            if time.monotonic() - started >= settings.sse_max_seconds:
                yield sse("reconnect", {})
                return
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                yield sse(event_name, message["data"])
            if time.monotonic() - last_beat >= settings.sse_heartbeat_seconds:
                if await sessions.is_access_token_revoked(
                    _uid(payload), payload.get("jti", ""), issued_at_ms(payload), payload.get("sid")
                ):
                    yield sse("reauth", {})  # signed out (this device or all devices)
                    return
                last_beat = time.monotonic()
                yield ": ping\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


def _uid(payload: dict[str, Any]) -> Any:
    import uuid

    return uuid.UUID(payload["sub"])
