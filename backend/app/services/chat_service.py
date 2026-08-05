"""ChatService — chatroom and message business logic."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.exceptions import (
    ForbiddenError,
    MessageIdempotencyError,
    NotFoundError,
    ValidationError,
)
from app.models.chatroom import Chatroom
from app.models.message import Message
from app.models.message_media import MessageMedia
from app.repositories.chatroom_read_repository import ChatroomReadRepository
from app.repositories.group_repository import (
    ChatroomRepository,
    GroupRepository,
    MembershipRepository,
)
from app.repositories.message_media_repository import MessageMediaRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository
from app.schemas.chat import MessageMediaIn, MessageMediaOut, MessageOut


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._chatroom_repo = ChatroomRepository(db)
        self._message_repo = MessageRepository(db)
        self._membership_repo = MembershipRepository(db)
        self._group_repo = GroupRepository(db)
        self._user_repo = UserRepository(db)
        self._chatroom_read_repo = ChatroomReadRepository(db)
        self._media_repo = MessageMediaRepository(db)

    async def get_chatroom_or_404(self, chatroom_id: str) -> Chatroom:
        chatroom = await self._chatroom_repo.get_by_id(chatroom_id)
        if chatroom is None:
            raise NotFoundError("Chatroom", chatroom_id)
        return chatroom

    async def list_group_chatrooms(self, group_id: str) -> list[Chatroom]:
        """Return all chatrooms for a group (main + topic chatrooms)."""
        return await self._chatroom_repo.list_by_group(group_id)

    async def get_chatroom_in_group_or_404(self, chatroom_id: str, group_id: str) -> Chatroom:
        """Load chatroom and verify it belongs to the given group (prevents IDOR)."""
        chatroom = await self._chatroom_repo.get_by_id(chatroom_id)
        if chatroom is None or chatroom.group_id != group_id:
            raise NotFoundError("Chatroom", chatroom_id)
        return chatroom

    async def require_member_access(self, chatroom_id: str, user_id: str) -> Chatroom:
        """Load the chatroom, verify its group is still alive (not soft-deleted)
        and that the user is a member. The WS join/send_message paths bypass
        GroupService, so the not-deleted check is enforced here via the same
        filtered GroupRepository.get_by_id used by GroupService."""
        chatroom = await self.get_chatroom_or_404(chatroom_id)
        group = await self._group_repo.get_by_id(chatroom.group_id)
        if group is None:
            raise NotFoundError("Group", chatroom.group_id)
        membership = await self._membership_repo.get(chatroom.group_id, user_id)
        if membership is None:
            raise ForbiddenError("You are not a member of this group")
        return chatroom

    @staticmethod
    def validate_object_key_for_chatroom(chatroom_id: str, object_key: str) -> None:
        """Reject object keys that were not minted for this chatroom (BOLA guard).

        The presign endpoint always mints keys shaped `chat/{chatroom_id}/{uuid4}`.
        Without this check a member of group B could attach an object_key they
        merely observed (from group A's presign response, or from a message they
        once had access to), and the presigned GET issued for their own message
        would hand their groupmates read access to an object they were never
        authorized to see. Same threat and same shape as
        TopicService.validate_object_key_for_topic.
        """
        prefix = f"chat/{chatroom_id}/"
        if not object_key.startswith(prefix):
            raise ValidationError("object_key does not belong to this chatroom")
        suffix = object_key[len(prefix) :]
        if not suffix or "/" in suffix:
            raise ValidationError("object_key must be a single path segment under this chatroom")

    def _validate_media(
        self, chatroom_id: str, media: list[MessageMediaIn]
    ) -> list[dict[str, object]]:
        """Re-validate client-claimed attachments and normalise them for the repo.

        Everything on the WS frame is client-supplied. The pydantic model already
        checked the MIME allowlist and the per-kind cap; this adds the count limit
        and the per-chatroom key guard, which need context the schema lacks.
        """
        if len(media) > storage.MAX_MEDIA_PER_MESSAGE:
            raise ValidationError(
                f"a message may carry at most {storage.MAX_MEDIA_PER_MESSAGE} attachments"
            )
        seen: set[str] = set()
        items: list[dict[str, object]] = []
        for m in media:
            self.validate_object_key_for_chatroom(chatroom_id, m.object_key)
            # Two rows pointing at the same object would render the same picture
            # twice and double-count against the limit.
            if m.object_key in seen:
                raise ValidationError("duplicate object_key in media")
            seen.add(m.object_key)
            items.append(
                {
                    "object_key": m.object_key,
                    "content_type": m.content_type,
                    "width": m.width,
                    "height": m.height,
                    "byte_size": m.byte_size,
                    # duration only makes sense for video; drop a stray value on
                    # an image so the row can't claim a bogus length.
                    "duration": m.duration if m.content_type in storage.VIDEO_MIME_TYPES else None,
                }
            )
        return items

    async def send_message(
        self,
        chatroom_id: str,
        sender_id: str,
        body: str,
        client_msg_id: str | None = None,
        media: list[MessageMediaIn] | None = None,
    ) -> tuple[Message, list[MessageMedia], bool]:
        """Return (message, media_rows, is_new).

        Raises MessageIdempotencyError on duplicate, ValidationError when the
        payload carries neither text nor attachments, or when an attachment
        fails the allowlist/cap/key checks.

        The message row and its media rows are written in ONE transaction: there
        is no confirm endpoint, so a partial write would leave a message that
        renders as blank text with no picture.
        """
        media = media or []
        if not body and not media:
            raise ValidationError("message must have a body or at least one attachment")
        media_values = self._validate_media(chatroom_id, media)

        if client_msg_id:
            existing = await self._message_repo.get_by_client_msg_id(sender_id, client_msg_id)
            if existing:
                raise MessageIdempotencyError()
        message = await self._message_repo.create(
            chatroom_id=chatroom_id,
            body=body,
            sender_id=sender_id,
            client_msg_id=client_msg_id,
        )
        media_rows: list[MessageMedia] = []
        if media_values:
            media_rows = await self._media_repo.create_many(message.id, media_values)
        await self._db.commit()
        await self._db.refresh(message)
        return message, media_rows, True

    async def presign_media_view(self, chatroom_id: str, media_id: str) -> MessageMediaOut:
        """Reissue the inline (viewing) URL for one attachment.

        History pages in older messages as the user scrolls, and those URLs
        expire independently. Refetching the newest page would not contain an
        older message at all, so its picture would stay broken forever — hence
        a per-attachment refresh rather than a page reload.
        """
        media = await self._media_repo.get_in_chatroom(media_id, chatroom_id)
        if media is None:
            raise NotFoundError("Media", media_id)
        return self.media_out([media])[0]

    async def presign_media_download(self, chatroom_id: str, media_id: str) -> str:
        """Signed URL that saves the attachment instead of opening it.

        Caller must have already passed the membership gate. The repository
        join re-checks that this attachment really belongs to this chatroom, so
        a guessed media_id from another group cannot be downloaded.
        """
        media = await self._media_repo.get_in_chatroom(media_id, chatroom_id)
        if media is None:
            raise NotFoundError("Media", media_id)
        return storage.presign_get(
            media.object_key,
            download_filename=storage.download_filename_for(media.id, media.type),
        )

    @staticmethod
    def media_out(rows: list[MessageMedia]) -> list[MessageMediaOut]:
        """Attach a short-TTL presigned GET to each row (access policy B)."""
        return [
            MessageMediaOut(
                id=r.id,
                url=storage.presign_get(r.object_key),
                content_type=r.type,
                width=r.width,
                height=r.height,
                byte_size=r.byte_size,
                duration=r.duration,
            )
            for r in rows
        ]

    async def get_main_chatroom(self, group_id: str) -> Chatroom:
        chatroom = await self._chatroom_repo.get_main_by_group(group_id)
        if chatroom is None:
            raise NotFoundError("Chatroom", f"main:{group_id}")
        return chatroom

    async def post_system_message(self, chatroom_id: str, body: str) -> Message:
        """Persist a system message (sender_id/client_msg_id null, type=system)."""
        message = await self._message_repo.create(
            chatroom_id=chatroom_id, body=body, sender_id=None, type="system"
        )
        await self._db.commit()
        await self._db.refresh(message)
        return message

    async def post_user_message(self, chatroom_id: str, sender_id: str, body: str) -> Message:
        """Persist a server-initiated message attributed to a user (e.g. the
        new-topic announcement posted by the topic author)."""
        message = await self._message_repo.create(
            chatroom_id=chatroom_id,
            body=body,
            sender_id=sender_id,
            type="user",
        )
        await self._db.commit()
        await self._db.refresh(message)
        return message

    async def list_messages(
        self,
        chatroom_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Message], str | None]:
        return await self._message_repo.list_by_chatroom(chatroom_id, cursor=cursor, limit=limit)

    async def list_messages_out(
        self,
        chatroom_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[MessageOut], str | None]:
        """History enriched with each message's sender nickname and attachments."""
        messages, next_cursor = await self._message_repo.list_by_chatroom(
            chatroom_id, cursor=cursor, limit=limit
        )
        nicknames: dict[str, str] = {}
        avatars: dict[str, str | None] = {}
        for sid in {m.sender_id for m in messages if m.sender_id}:
            user = await self._user_repo.get_by_id(sid)
            if user:
                nicknames[sid] = user.nickname
                avatars[sid] = user.avatar_url

        # One query for the whole page, then group in memory — a per-message
        # lookup here would be an N+1 on every history load and every scroll.
        media_by_message: dict[str, list[MessageMedia]] = {}
        for row in await self._media_repo.list_by_message_ids([m.id for m in messages]):
            media_by_message.setdefault(row.message_id, []).append(row)

        out = [
            MessageOut(
                id=m.id,
                chatroom_id=m.chatroom_id,
                sender_id=m.sender_id,
                sender_nickname=nicknames.get(m.sender_id) if m.sender_id else None,
                sender_avatar_url=avatars.get(m.sender_id) if m.sender_id else None,
                client_msg_id=m.client_msg_id,
                body=m.body,
                type=m.type,
                created_at=m.created_at,
                media=self.media_out(media_by_message.get(m.id, [])),
            )
            for m in messages
        ]
        return out, next_cursor

    async def mark_read(
        self, chatroom_id: str, user_id: str, up_to: datetime | None = None
    ) -> None:
        """Mark chatroom as read for the user and clear topic notifications if applicable.

        The receipt is recorded up to `up_to` (the newest message the client has
        actually rendered), capped at now — so a message that arrived in the
        REST/WS entry gap and was never seen by the client is not covered. When
        `up_to` is omitted, falls back to now. Commits once.
        """
        from app.services.notification_service import NotificationService

        chatroom = await self.get_chatroom_or_404(chatroom_id)
        now = datetime.now(timezone.utc)
        if up_to is not None:
            if up_to.tzinfo is None:
                up_to = up_to.replace(tzinfo=timezone.utc)
            read_ts = min(up_to, now)
        else:
            read_ts = now
        await self._chatroom_read_repo.upsert(
            user_id=user_id, chatroom_id=chatroom_id, last_read_at=read_ts
        )
        await self._db.commit()

        if chatroom.topic_id:
            notif_svc = NotificationService(self._db)
            # Bound the clear to the same read point: a chat_unread for a message
            # after read_ts must survive (the topic still computes as unread).
            await notif_svc.clear_topic_notifications(
                user_id=user_id, topic_id=chatroom.topic_id, before=read_ts
            )

    async def on_topic_message_posted(
        self, chatroom_id: str, sender_id: str, message_at: datetime
    ) -> None:
        """Called after a message is sent in a topic chatroom.

        Loads chatroom + topic + group + members, then bumps chat_unread
        notifications for all members except the sender, stamping each with the
        message's timestamp. No-op if chatroom is not a topic chatroom.
        """
        from app.repositories.topic_repository import TopicRepository
        from app.services.notification_service import NotificationService
        from app.services.push_dispatch import schedule_push_dispatch

        chatroom = await self.get_chatroom_or_404(chatroom_id)
        if chatroom.type != "topic" or not chatroom.topic_id:
            return

        topic_repo = TopicRepository(self._db)
        topic = await topic_repo.get_by_id(chatroom.topic_id)
        if topic is None:
            return

        group_repo = GroupRepository(self._db)
        group = await group_repo.get_by_id(chatroom.group_id)
        if group is None:
            return

        membership_repo = MembershipRepository(self._db)
        memberships = await membership_repo.list_by_group(chatroom.group_id)
        member_user_ids = [m.user_id for m in memberships]

        notif_svc = NotificationService(self._db)
        await notif_svc.bump_topic_unread(
            group_id=chatroom.group_id,
            topic_id=topic.id,
            topic_title=topic.title,
            group_name=group.name,
            exclude_user_id=sender_id,
            member_user_ids=member_user_ids,
            message_at=message_at,
        )

        # Web Push (M1): fire-and-forget, never blocks the message-send flow.
        recipient_ids = [uid for uid in member_user_ids if uid != sender_id]
        schedule_push_dispatch(
            recipient_ids,
            {
                "title": group.name,
                "body": f"{topic.title}에 대해 안 읽은 채팅이 있어요",
                "url": f"/groups/{chatroom.group_id}/topics/{topic.id}/chat",
            },
        )
