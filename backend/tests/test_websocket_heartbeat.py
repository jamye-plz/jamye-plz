"""Regression coverage for the additive WebSocket heartbeat protocol."""

from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect

from app.core import ws_hub
from app.core.exceptions import ForbiddenError, NotFoundError
from app.main import websocket_endpoint


class ScriptedWebSocket:
    """Minimal authenticated socket that supplies a finite sequence of frames."""

    def __init__(self, frames: list[dict[str, str]]) -> None:
        self.cookies = {"access_token": "test-token"}
        self._frames = iter(frames)
        self.accepted = False
        self.sent: list[dict[str, str]] = []
        self.closed_with: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def receive_json(self) -> dict[str, str]:
        try:
            return next(self._frames)
        except StopIteration as exc:
            raise WebSocketDisconnect() from exc

    async def send_json(self, message: dict[str, str]) -> None:
        self.sent.append(message)

    async def close(self, code: int) -> None:
        self.closed_with = code


@pytest.fixture(autouse=True)
def reset_ws_hub_state() -> None:
    """Keep the process-global registry isolated from other socket tests."""
    ws_hub._connections.clear()
    ws_hub._socket_users.clear()
    yield
    ws_hub._connections.clear()
    ws_hub._socket_users.clear()


async def test_ping_returns_direct_pong_without_mutating_socket_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ping is an additive liveness frame, not a join, broadcast, or DB action."""
    lookup_count = 0

    def fake_decode_access_token(token: str) -> dict[str, str]:
        assert token == "test-token"
        return {"sub": "user-1"}

    async def fake_get_db():
        yield object()

    async def fake_get_by_id(self: object, user_id: str) -> SimpleNamespace:
        nonlocal lookup_count
        assert user_id == "user-1"
        lookup_count += 1
        return SimpleNamespace(nickname="보비", avatar_url=None)

    monkeypatch.setattr("app.core.security.decode_access_token", fake_decode_access_token)
    monkeypatch.setattr("app.db.session.get_db", fake_get_db)
    monkeypatch.setattr("app.repositories.user_repository.UserRepository.get_by_id", fake_get_by_id)

    websocket = ScriptedWebSocket([{"type": "ping"}, {"type": "unexpected"}])

    await websocket_endpoint(websocket)  # type: ignore[arg-type]

    assert websocket.accepted is True
    assert websocket.sent == [
        {"type": "pong"},
        {"type": "error", "detail": "Unknown message type: unexpected"},
    ]
    assert lookup_count == 1
    assert ws_hub._connections == {}
    assert ws_hub._socket_users == {}


async def test_join_acknowledges_only_after_socket_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The joined frame is the causal boundary for client history recovery."""

    class SubscriptionCheckingWebSocket(ScriptedWebSocket):
        async def send_json(self, message: dict[str, str]) -> None:
            if message.get("type") == "joined":
                assert self in ws_hub._connections.get("room-1", set())
            await super().send_json(message)

    def fake_decode_access_token(token: str) -> dict[str, str]:
        return {"sub": "user-1"}

    async def fake_get_db():
        yield object()

    async def fake_get_by_id(self: object, user_id: str) -> SimpleNamespace:
        return SimpleNamespace(nickname="보비", avatar_url=None)

    async def allow_join(self: object, chatroom_id: str, user_id: str) -> SimpleNamespace:
        return SimpleNamespace(id=chatroom_id)

    monkeypatch.setattr("app.core.security.decode_access_token", fake_decode_access_token)
    monkeypatch.setattr("app.db.session.get_db", fake_get_db)
    monkeypatch.setattr("app.repositories.user_repository.UserRepository.get_by_id", fake_get_by_id)
    monkeypatch.setattr("app.services.chat_service.ChatService.require_member_access", allow_join)

    websocket = SubscriptionCheckingWebSocket([{"type": "join", "chatroom_id": "room-1"}])

    await websocket_endpoint(websocket)  # type: ignore[arg-type]

    assert websocket.sent == [{"type": "joined", "chatroom_id": "room-1"}]
    assert websocket.closed_with is None
    assert ws_hub._connections == {}
    assert ws_hub._socket_users == {}


@pytest.mark.parametrize(
    "join_error",
    [ForbiddenError("membership revoked"), NotFoundError("Chatroom", "room-1")],
)
async def test_rejected_join_closes_with_terminal_eviction_code(
    monkeypatch: pytest.MonkeyPatch,
    join_error: ForbiddenError | NotFoundError,
) -> None:
    """A rejected reconnect must reuse the client's 4001 cache cleanup path."""

    def fake_decode_access_token(token: str) -> dict[str, str]:
        return {"sub": "user-1"}

    async def fake_get_db():
        yield object()

    async def fake_get_by_id(self: object, user_id: str) -> SimpleNamespace:
        return SimpleNamespace(nickname="보비", avatar_url=None)

    async def reject_join(self: object, chatroom_id: str, user_id: str) -> None:
        raise join_error

    monkeypatch.setattr("app.core.security.decode_access_token", fake_decode_access_token)
    monkeypatch.setattr("app.db.session.get_db", fake_get_db)
    monkeypatch.setattr("app.repositories.user_repository.UserRepository.get_by_id", fake_get_by_id)
    monkeypatch.setattr("app.services.chat_service.ChatService.require_member_access", reject_join)

    websocket = ScriptedWebSocket([{"type": "join", "chatroom_id": "room-1"}])

    await websocket_endpoint(websocket)  # type: ignore[arg-type]

    assert websocket.sent == []
    assert websocket.closed_with == ws_hub.EVICTED_CLOSE_CODE
    assert ws_hub._connections == {}
    assert ws_hub._socket_users == {}
