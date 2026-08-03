"""Unit tests for the in-process WS connection registry (app.core.ws_hub).

Covers the user-tracked eviction path added for QA finding HIGH-2: a member
removed from (or leaving) a group must have their live sockets disconnected
so they stop receiving further broadcasts for that group's chatrooms.
"""

import pytest

from app.core import ws_hub

CHATROOM_ID = "chatroom-1"
USER_A = "user-a"
USER_B = "user-b"


class FakeWebSocket:
    """Duck-typed stand-in for fastapi.WebSocket — no real network I/O."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.sent: list[dict] = []
        self.closed_with: int | None = None

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)

    async def close(self, code: int = 1000) -> None:
        self.closed_with = code


@pytest.fixture(autouse=True)
def _reset_ws_hub_state():
    """ws_hub keeps process-global registries; isolate each test from the next."""
    ws_hub._connections.clear()
    ws_hub._socket_users.clear()
    yield
    ws_hub._connections.clear()
    ws_hub._socket_users.clear()


async def test_evict_user_closes_and_removes_only_that_users_sockets() -> None:
    ws_a = FakeWebSocket("a")
    ws_b = FakeWebSocket("b")
    ws_hub.join(CHATROOM_ID, ws_a, USER_A)
    ws_hub.join(CHATROOM_ID, ws_b, USER_B)

    await ws_hub.evict_user([CHATROOM_ID], USER_A)

    assert ws_a.closed_with == ws_hub.EVICTED_CLOSE_CODE
    assert ws_b.closed_with is None
    assert ws_a not in ws_hub._connections[CHATROOM_ID]
    assert ws_b in ws_hub._connections[CHATROOM_ID]
    assert ws_a not in ws_hub._socket_users
    assert ws_hub._socket_users[ws_b] == USER_B


async def test_broadcast_skips_evicted_user() -> None:
    ws_a = FakeWebSocket("a")
    ws_b = FakeWebSocket("b")
    ws_hub.join(CHATROOM_ID, ws_a, USER_A)
    ws_hub.join(CHATROOM_ID, ws_b, USER_B)

    await ws_hub.evict_user([CHATROOM_ID], USER_A)
    await ws_hub.broadcast(CHATROOM_ID, {"type": "message", "body": "hi"})

    assert ws_a.sent == []
    assert ws_b.sent == [{"type": "message", "body": "hi"}]


async def test_evict_user_is_noop_for_unrelated_user() -> None:
    ws_a = FakeWebSocket("a")
    ws_hub.join(CHATROOM_ID, ws_a, USER_A)

    await ws_hub.evict_user([CHATROOM_ID], USER_B)

    assert ws_a.closed_with is None
    assert ws_a in ws_hub._connections[CHATROOM_ID]


async def test_leave_forgets_user_mapping_once_no_rooms_remain() -> None:
    ws_a = FakeWebSocket("a")
    ws_hub.join(CHATROOM_ID, ws_a, USER_A)
    ws_hub.leave(CHATROOM_ID, ws_a)

    assert ws_a not in ws_hub._connections.get(CHATROOM_ID, set())
    assert ws_a not in ws_hub._socket_users


async def test_evict_user_sweeps_every_room_it_is_told_about() -> None:
    ws_a = FakeWebSocket("a")
    ws_hub.join("room-1", ws_a, USER_A)
    ws_hub._connections.setdefault("room-2", set()).add(ws_a)

    await ws_hub.evict_user(["room-1", "room-2"], USER_A)

    assert ws_a not in ws_hub._connections["room-1"]
    assert ws_a not in ws_hub._connections["room-2"]
    assert ws_a.closed_with == ws_hub.EVICTED_CLOSE_CODE


async def test_evict_user_swallows_close_errors() -> None:
    """A socket that raises on close() must still be removed from the
    registry — eviction is best-effort and must not propagate."""

    class BoomingWebSocket(FakeWebSocket):
        async def close(self, code: int = 1000) -> None:
            raise RuntimeError("socket already gone")

    ws_a = BoomingWebSocket("a")
    ws_hub.join(CHATROOM_ID, ws_a, USER_A)

    await ws_hub.evict_user([CHATROOM_ID], USER_A)  # must not raise

    assert ws_a not in ws_hub._connections[CHATROOM_ID]
    assert ws_a not in ws_hub._socket_users
