"""FastAPI application entry point.

Registers all routers, CORS middleware, exception handlers,
and the WebSocket /api/ws endpoint.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.routers import (
    auth,
    chatrooms,
    groups,
    invites,
    media,
    me,
    notifications,
    push,
    tags,
    topics,
)

logger = logging.getLogger(__name__)

# ── App factory ───────────────────────────────────────────────────────────────

settings = get_settings()

app = FastAPI(
    title="jamye-plz API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# ── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ────────────────────────────────────────────────────────


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "detail": "Internal server error"},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

API_PREFIX = "/api"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(me.router, prefix=API_PREFIX)
app.include_router(groups.router, prefix=API_PREFIX)
app.include_router(invites.router, prefix=API_PREFIX)
app.include_router(invites.redeem_router, prefix=API_PREFIX)
app.include_router(topics.router, prefix=API_PREFIX)
app.include_router(media.router, prefix=API_PREFIX)
app.include_router(tags.router, prefix=API_PREFIX)
app.include_router(chatrooms.router, prefix=API_PREFIX)
app.include_router(push.router, prefix=API_PREFIX)
app.include_router(notifications.router, prefix=API_PREFIX)


# ── WebSocket /api/ws ─────────────────────────────────────────────────────────

# Connection registry + broadcast live in app.core.ws_hub so HTTP handlers
# (e.g. new-topic reminders) can fan out to the same subscribers.
from app.core import ws_hub


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket handler.

    Authentication via httpOnly cookie `access_token`.
    Protocol (JSON messages):
      Client → Server:
        { "type": "join",         "chatroom_id": "..." }
        { "type": "send_message", "chatroom_id": "...", "body": "...", "client_msg_id": "..." }
        { "type": "ack",          "message_id": "..." }

      Server → Client:
        { "type": "message",   ...MessageOut fields }
        { "type": "duplicate", "message_id": "..." }
        { "type": "system",    "body": "..." }
        { "type": "error",     "detail": "..." }
    """
    # ── Auth via cookie ───────────────────────────────────────────────────────
    from app.core.security import decode_access_token
    from app.core.exceptions import AuthenticationError
    from app.db.session import get_db
    from app.repositories.user_repository import UserRepository
    from app.services.chat_service import ChatService
    from app.services.group_service import GroupService
    from app.core.exceptions import MessageIdempotencyError

    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Token missing subject")
    except AuthenticationError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    # Resolve the sender's nickname + avatar once for this connection.
    sender_nickname: str | None = None
    sender_avatar_url: str | None = None
    async for db in get_db():
        sender = await UserRepository(db).get_by_id(user_id)
        if sender:
            sender_nickname = sender.nickname
            sender_avatar_url = sender.avatar_url
        break

    active_chatroom: str | None = None

    try:
        while True:
            data: dict[str, Any] = await websocket.receive_json()
            msg_type: str = data.get("type", "")

            if msg_type == "join":
                chatroom_id: str = data.get("chatroom_id", "")
                if not chatroom_id:
                    await websocket.send_json({"type": "error", "detail": "chatroom_id required"})
                    continue

                # Verify membership
                async for db in get_db():
                    try:
                        chat_svc = ChatService(db)
                        chatroom = await chat_svc.require_member_access(chatroom_id, user_id)
                        # Leave previous chatroom
                        if active_chatroom and active_chatroom != chatroom_id:
                            ws_hub.leave(active_chatroom, websocket)
                        active_chatroom = chatroom_id
                        ws_hub.join(chatroom_id, websocket)
                        await websocket.send_json(
                            {"type": "system", "body": f"Joined chatroom {chatroom_id}"}
                        )
                    except AppError as exc:
                        await websocket.send_json({"type": "error", "detail": exc.detail})
                    break

            elif msg_type == "send_message":
                chatroom_id = data.get("chatroom_id", "")
                body: str = data.get("body", "")
                client_msg_id: str | None = data.get("client_msg_id")

                if not chatroom_id or not body:
                    await websocket.send_json(
                        {"type": "error", "detail": "chatroom_id and body required"}
                    )
                    continue

                async for db in get_db():
                    try:
                        chat_svc = ChatService(db)
                        # Enforce group membership even if the client skipped `join`.
                        await chat_svc.require_member_access(chatroom_id, user_id)
                        message, _ = await chat_svc.send_message(
                            chatroom_id=chatroom_id,
                            sender_id=user_id,
                            body=body,
                            client_msg_id=client_msg_id,
                        )
                        msg_payload: dict[str, Any] = {
                            "type": "message",
                            "id": message.id,
                            "chatroom_id": message.chatroom_id,
                            "sender_id": message.sender_id,
                            "sender_nickname": sender_nickname,
                            "sender_avatar_url": sender_avatar_url,
                            "client_msg_id": message.client_msg_id,
                            "body": message.body,
                            "msg_type": message.type,
                            "created_at": message.created_at.isoformat(),
                        }
                        # Echo to sender
                        await websocket.send_json(msg_payload)
                        # Broadcast to other members
                        await ws_hub.broadcast(chatroom_id, msg_payload, exclude=websocket)
                    except MessageIdempotencyError:
                        await websocket.send_json(
                            {"type": "duplicate", "client_msg_id": client_msg_id}
                        )
                    except AppError as exc:
                        await websocket.send_json({"type": "error", "detail": exc.detail})
                    break

            elif msg_type == "ack":
                # Client acknowledges receipt — no server action required
                pass

            else:
                await websocket.send_json(
                    {"type": "error", "detail": f"Unknown message type: {msg_type}"}
                )

    except WebSocketDisconnect:
        pass
    finally:
        if active_chatroom:
            ws_hub.leave(active_chatroom, websocket)


# ── Health ────────────────────────────────────────────────────────────────────


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
