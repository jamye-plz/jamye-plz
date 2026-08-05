"""FastAPI application entry point.

Registers all routers, CORS middleware, exception handlers,
and the WebSocket /api/ws endpoint.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Pydantic's own error, NOT app.core.exceptions.ValidationError — the latter is
# an AppError subclass already handled by the `except AppError` arm below.
# Conflating the two would let a malformed media frame escape and kill the socket.
from pydantic import ValidationError as PydanticValidationError

from app.core import storage, ws_hub
from app.core.config import get_settings
from app.core.queue import close_arq_pool
from app.core.exceptions import AppError
from app.routers import (
    auth,
    chat_media,
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
from app.schemas.chat import MessageMediaIn

logger = logging.getLogger(__name__)

# ── App factory ───────────────────────────────────────────────────────────────

settings = get_settings()


async def _transcript_bridge() -> None:
    """Relay transcript events from the STT worker to chatroom sockets.

    The arq worker is a separate process and cannot reach this process's
    in-memory ws_hub, so it publishes results on a Redis channel and this
    task — the only subscriber — turns them into WS `transcript` frames.
    Reconnects with capped backoff; a Redis outage only delays transcripts
    (the rows are already persisted), it never affects message delivery.
    """
    import redis.asyncio as aioredis

    from app.core.queue import TRANSCRIPT_CHANNEL, parse_transcript_event

    backoff = 1.0
    while True:
        try:
            client = aioredis.from_url(settings.redis_url)
            try:
                pubsub = client.pubsub()
                await pubsub.subscribe(TRANSCRIPT_CHANNEL)
                backoff = 1.0
                async for msg in pubsub.listen():
                    if msg.get("type") != "message":
                        continue
                    frame = parse_transcript_event(msg["data"])
                    if frame is None:
                        continue
                    await ws_hub.broadcast(frame["chatroom_id"], frame)
            finally:
                await client.aclose()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "Transcript bridge lost Redis; retrying in %.0fs", backoff, exc_info=True
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.minio_enabled:
        try:
            await asyncio.to_thread(storage.ensure_bucket)
        except Exception:
            # Warn-only: a MinIO hiccup (e.g. homelab restart ordering) must
            # not prevent the API from serving traffic.
            logger.warning("Failed to ensure MinIO bucket exists at startup", exc_info=True)
    bridge_task: asyncio.Task[None] | None = None
    if settings.transcription_enabled:
        bridge_task = asyncio.create_task(_transcript_bridge())
    yield
    if bridge_task is not None:
        bridge_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await bridge_task
    await close_arq_pool()


app = FastAPI(
    title="jamye-plz API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
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
app.include_router(chat_media.router, prefix=API_PREFIX)
app.include_router(push.router, prefix=API_PREFIX)
app.include_router(notifications.router, prefix=API_PREFIX)


# ── WebSocket /api/ws ─────────────────────────────────────────────────────────
# Connection registry + broadcast live in app.core.ws_hub (imported at the top)
# so HTTP handlers (e.g. new-topic reminders) can fan out to the same subscribers.


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
                        await chat_svc.require_member_access(chatroom_id, user_id)
                        # Leave previous chatroom
                        if active_chatroom and active_chatroom != chatroom_id:
                            ws_hub.leave(active_chatroom, websocket)
                        active_chatroom = chatroom_id
                        ws_hub.join(chatroom_id, websocket, user_id)
                        # No join ack: it surfaced as a "Joined chatroom <uuid>"
                        # system line in the room. Errors still report via "error".
                    except AppError as exc:
                        await websocket.send_json({"type": "error", "detail": exc.detail})
                    break

            elif msg_type == "send_message":
                chatroom_id = data.get("chatroom_id", "")
                body: str = data.get("body", "")
                client_msg_id: str | None = data.get("client_msg_id")

                # A media-only message is legitimate (photo with no caption), so
                # `body` alone is no longer required — but a frame carrying
                # neither text nor attachments still is not a message.
                raw_media = data.get("media") or []
                if not chatroom_id or (not body and not raw_media):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "detail": "chatroom_id and either body or media required",
                        }
                    )
                    continue

                # Parse attachments up front: a malformed frame must not reach
                # the service (and must not look like a server fault).
                try:
                    media_in = [MessageMediaIn.model_validate(m) for m in raw_media]
                except (PydanticValidationError, TypeError) as exc:
                    await websocket.send_json(
                        {"type": "error", "detail": f"invalid media payload: {exc}"}
                    )
                    continue

                async for db in get_db():
                    try:
                        chat_svc = ChatService(db)
                        # Enforce group membership even if the client skipped `join`.
                        await chat_svc.require_member_access(chatroom_id, user_id)
                        message, media_rows, _ = await chat_svc.send_message(
                            chatroom_id=chatroom_id,
                            sender_id=user_id,
                            body=body,
                            client_msg_id=client_msg_id,
                            media=media_in,
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
                            "media": [m.model_dump() for m in ChatService.media_out(media_rows)],
                        }
                        # Echo to sender
                        await websocket.send_json(msg_payload)
                        # Recycle the per-topic "unread chat" notification BEFORE the
                        # fan-out (no-op for the group main chatroom): a recipient who
                        # is viewing the room marks it read the instant the broadcast
                        # arrives, so the notification must already exist for that read
                        # to clear it — otherwise it lingers as a phantom unread.
                        await chat_svc.on_topic_message_posted(
                            chatroom_id, user_id, message.created_at
                        )
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
