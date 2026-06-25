"""ChatService — chatroom and message business logic."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, MessageIdempotencyError, NotFoundError
from app.models.chatroom import Chatroom
from app.models.message import Message
from app.repositories.chatroom_read_repository import ChatroomReadRepository
from app.repositories.group_repository import ChatroomRepository, MembershipRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository
from app.schemas.chat import MessageOut


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._chatroom_repo = ChatroomRepository(db)
        self._message_repo = MessageRepository(db)
        self._membership_repo = MembershipRepository(db)
        self._user_repo = UserRepository(db)
        self._chatroom_read_repo = ChatroomReadRepository(db)

    async def get_chatroom_or_404(self, chatroom_id: str) -> Chatroom:
        chatroom = await self._chatroom_repo.get_by_id(chatroom_id)
        if chatroom is None:
            raise NotFoundError("Chatroom", chatroom_id)
        return chatroom

    async def list_group_chatrooms(self, group_id: str) -> list[Chatroom]:
        """Return all chatrooms for a group (main + topic chatrooms)."""
        from sqlalchemy import select
        from app.models.chatroom import Chatroom as ChatroomModel

        result = await self._db.execute(
            select(ChatroomModel).where(ChatroomModel.group_id == group_id)
        )
        return list(result.scalars().all())

    async def get_chatroom_in_group_or_404(self, chatroom_id: str, group_id: str) -> Chatroom:
        """Load chatroom and verify it belongs to the given group (prevents IDOR)."""
        chatroom = await self._chatroom_repo.get_by_id(chatroom_id)
        if chatroom is None or chatroom.group_id != group_id:
            raise NotFoundError("Chatroom", chatroom_id)
        return chatroom

    async def require_member_access(self, chatroom_id: str, user_id: str) -> Chatroom:
        chatroom = await self.get_chatroom_or_404(chatroom_id)
        membership = await self._membership_repo.get(chatroom.group_id, user_id)
        if membership is None:
            raise ForbiddenError("You are not a member of this group")
        return chatroom

    async def send_message(
        self,
        chatroom_id: str,
        sender_id: str,
        body: str,
        client_msg_id: str | None = None,
    ) -> tuple[Message, bool]:
        """Return (message, is_new). Raises MessageIdempotencyError on duplicate."""
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
        await self._db.commit()
        await self._db.refresh(message)
        return message, True

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
        """History enriched with each message's sender nickname."""
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
            )
            for m in messages
        ]
        return out, next_cursor

    async def mark_read(self, chatroom_id: str, user_id: str) -> None:
        """Mark chatroom as read for the user and clear topic notifications if applicable.

        Upserts a ChatroomRead and, if the chatroom is a topic chatroom,
        calls NotificationService.clear_topic_notifications.
        Commits once.
        """
        from app.services.notification_service import NotificationService

        chatroom = await self.get_chatroom_or_404(chatroom_id)
        now = datetime.now(timezone.utc)
        await self._chatroom_read_repo.upsert(
            user_id=user_id, chatroom_id=chatroom_id, last_read_at=now
        )
        await self._db.commit()

        if chatroom.topic_id:
            notif_svc = NotificationService(self._db)
            # Bound the clear to `now`: a chat_unread created by a message that
            # arrived after this read receipt must survive (the topic still
            # computes as unread, so the alert has to stay).
            await notif_svc.clear_topic_notifications(
                user_id=user_id, topic_id=chatroom.topic_id, before=now
            )

    async def on_topic_message_posted(self, chatroom_id: str, sender_id: str) -> None:
        """Called after a message is sent in a topic chatroom.

        Loads chatroom + topic + group + members, then bumps chat_unread
        notifications for all members except the sender.
        No-op if chatroom is not a topic chatroom.
        """
        from app.repositories.group_repository import GroupRepository, MembershipRepository
        from app.repositories.topic_repository import TopicRepository
        from app.services.notification_service import NotificationService

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
        )
