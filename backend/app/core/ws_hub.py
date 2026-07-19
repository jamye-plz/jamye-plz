"""In-process WebSocket connection registry and broadcast.

Single-process pub/sub for chat fan-out, shared by the `/api/ws` handler and
HTTP handlers that need to push system messages (e.g. new-topic reminders).
Swap for Redis pub/sub to scale beyond one process.
"""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket

# Code used to close a socket that has been evicted because its user is no
# longer a member of the group backing the room (removed/left/kicked). In the
# 4000-4999 private-use range, distinct from the standard 1008 policy-violation
# code used for auth failures.
EVICTED_CLOSE_CODE = 4001

# chatroom_id -> set of live WebSocket connections
_connections: dict[str, set[WebSocket]] = {}

# WebSocket -> user_id, recorded on join so a user's sockets can be evicted
# (e.g. after group removal) without the caller having to track them.
_socket_users: dict[WebSocket, str] = {}


def join(chatroom_id: str, ws: WebSocket, user_id: str) -> None:
    _connections.setdefault(chatroom_id, set()).add(ws)
    _socket_users[ws] = user_id


def leave(chatroom_id: str, ws: WebSocket) -> None:
    _connections.get(chatroom_id, set()).discard(ws)
    _forget_if_orphaned(ws)


def _forget_if_orphaned(ws: WebSocket) -> None:
    """Drop the ws -> user_id mapping once the socket is in no more rooms."""
    if not any(ws in sockets for sockets in _connections.values()):
        _socket_users.pop(ws, None)


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
        _forget_if_orphaned(ws)


async def evict_user(chatroom_ids: list[str], user_id: str) -> None:
    """Forcibly disconnect `user_id`'s live sockets from the given rooms.

    Used when a member is removed from (or leaves) a group so they stop
    receiving broadcasts for chatrooms they no longer belong to. Removes the
    socket from the registry first so a slow/failing close() can't leave a
    stale entry that still receives broadcast fan-out.
    """
    for chatroom_id in chatroom_ids:
        sockets = _connections.get(chatroom_id, set()).copy()
        for ws in sockets:
            if _socket_users.get(ws) != user_id:
                continue
            _connections.get(chatroom_id, set()).discard(ws)
            _forget_if_orphaned(ws)
            try:
                await ws.close(code=EVICTED_CLOSE_CODE)
            except Exception:
                pass


async def evict_room(chatroom_ids: list[str]) -> None:
    """Forcibly disconnect *every* live socket from the given rooms.

    Used when a whole group is deleted: unlike `evict_user` (which targets one
    member), this drops all members' sockets so no in-flight broadcast can fan
    out to a chatroom that just became inaccessible. Removes each socket from
    the registry before closing so a slow close() can't keep receiving fan-out.
    """
    for chatroom_id in chatroom_ids:
        sockets = _connections.get(chatroom_id, set()).copy()
        for ws in sockets:
            _connections.get(chatroom_id, set()).discard(ws)
            _forget_if_orphaned(ws)
            try:
                await ws.close(code=EVICTED_CLOSE_CODE)
            except Exception:
                pass
