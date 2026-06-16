"""ChatService — chatroom and message business logic."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, MessageIdempotencyError, NotFoundError
from app.models.chatroom import Chatroom
from app.models.message import Message
from app.repositories.group_repository import ChatroomRepository, MembershipRepository
from app.repositories.message_repository import MessageRepository


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._chatroom_repo = ChatroomRepository(db)
        self._message_repo = MessageRepository(db)
        self._membership_repo = MembershipRepository(db)

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
            existing = await self._message_repo.get_by_client_msg_id(
                sender_id, client_msg_id
            )
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

    async def list_messages(
        self,
        chatroom_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Message], str | None]:
        return await self._message_repo.list_by_chatroom(
            chatroom_id, cursor=cursor, limit=limit
        )
