"""Regression coverage for the additive WebSocket heartbeat protocol."""

from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect

from app.core import ws_hub
from app.main import websocket_endpoint


class ScriptedWebSocket:
    """Minimal authenticated socket that supplies a finite sequence of frames."""

    def __init__(self, frames: list[dict[str, str]]) -> None:
        self.cookies = {"access_token": "test-token"}
        self._frames = iter(frames)
        self.accepted = False
        self.sent: list[dict[str, str]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def receive_json(self) -> dict[str, str]:
        try:
            return next(self._frames)
        except StopIteration as exc:
            raise WebSocketDisconnect() from exc

    async def send_json(self, message: dict[str, str]) -> None:
        self.sent.append(message)


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
