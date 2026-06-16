"""In-process WebSocket connection registry and broadcast.

Single-process pub/sub for chat fan-out, shared by the `/api/ws` handler and
HTTP handlers that need to push system messages (e.g. new-topic reminders).
Swap for Redis pub/sub to scale beyond one process.
"""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket

# chatroom_id -> set of live WebSocket connections
_connections: dict[str, set[WebSocket]] = {}


def join(chatroom_id: str, ws: WebSocket) -> None:
    _connections.setdefault(chatroom_id, set()).add(ws)


def leave(chatroom_id: str, ws: WebSocket) -> None:
    _connections.get(chatroom_id, set()).discard(ws)


async def broadcast(
    chatroom_id: str, message: dict[str, Any], exclude: WebSocket | None = None
) -> None:
    """Send a JSON message to every connection subscribed to a chatroom."""
    sockets = _connections.get(chatroom_id, set()).copy()
    dead: set[WebSocket] = set()
    for ws in sockets:
        if ws is exclude:
            continue
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _connections.get(chatroom_id, set()).discard(ws)
