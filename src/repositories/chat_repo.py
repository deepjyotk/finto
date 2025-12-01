"""Chat repository - pure class for data access, no FastAPI imports"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import ChatMessageType
from src.models.chat_messages import ChatMessage
from src.models.chat_session import ChatSession


class ChatRepository:
    """Repository for ChatSession data access operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, user_id: UUID) -> ChatSession:
        """
        Create a new chat session.

        Args:
            user_id: The user ID for the session

        Returns:
            ChatSession object
        """
        chat_session = ChatSession(user_id=user_id)
        self.session.add(chat_session)
        await self.session.flush()
        return chat_session

    async def get_session_by_id(self, chat_session_id: UUID) -> ChatSession | None:
        """
        Get a chat session by ID.

        Args:
            chat_session_id: The session ID to search for

        Returns:
            ChatSession object if found, None otherwise
        """
        result = await self.session.execute(
            select(ChatSession).where(ChatSession.chat_session_id == chat_session_id)
        )
        return result.scalar_one_or_none()

    async def get_sessions_by_user_id(self, user_id: UUID) -> list[ChatSession]:
        """
        Get all chat sessions for a user.

        Args:
            user_id: The user ID to search for

        Returns:
            List of ChatSession objects
        """
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.started_at.desc())
        )
        return list(result.scalars().all())

    async def get_next_seq_no(self, session_id: UUID) -> int:
        """
        Get the next sequence number for a chat session.

        Args:
            session_id: The session ID

        Returns:
            The next sequence number (1 if no messages exist yet)
        """
        result = await self.session.execute(
            select(func.coalesce(func.max(ChatMessage.seq_no), 0)).where(
                ChatMessage.session_id == session_id
            )
        )
        max_seq = result.scalar() or 0
        return max_seq + 1

    async def get_thread_root_id(self, session_id: UUID) -> UUID | None:
        """
        Get the thread root ID for a session (the ID of the first user message).

        Args:
            session_id: The session ID

        Returns:
            The thread root ID if messages exist, None if this is the first message
        """
        # Get any existing message's thread_root_id (all messages in a thread should have the same root)
        result = await self.session.execute(
            select(ChatMessage.thread_root_id)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.thread_root_id.isnot(None))
            .limit(1)
        )
        thread_root = result.scalar_one_or_none()
        return thread_root

    async def create_user_message(
        self,
        session_id: UUID,
        user_id: UUID,
        content: str,
        reply_to_id: UUID | None = None,
        thread_root_id: UUID | None = None,
    ) -> ChatMessage:
        """
        Create a user message in the chat_messages table.

        If thread_root_id is not provided, it will be automatically determined:
        - If this is the first message in the session, thread_root_id will be set to this message's ID
        - Otherwise, it will use the existing thread_root_id from previous messages

        Args:
            session_id: The chat session ID
            user_id: The user ID (required for user messages)
            content: The message content
            reply_to_id: Optional ID of the message this is replying to
            thread_root_id: Optional ID of the root message in a thread (auto-determined if None)

        Returns:
            The created ChatMessage object
        """
        seq_no = await self.get_next_seq_no(session_id)

        # If thread_root_id is not provided, determine it automatically
        if thread_root_id is None:
            existing_thread_root = await self.get_thread_root_id(session_id)
            thread_root_id = existing_thread_root

        message = ChatMessage(
            session_id=session_id,
            seq_no=seq_no,
            user_id=user_id,
            content=content,
            message_type=ChatMessageType.USER,
            reply_to_id=reply_to_id,
            thread_root_id=thread_root_id,
        )
        self.session.add(message)
        await self.session.flush()

        # If this is the first message (no existing thread root), set thread_root_id to this message's ID
        if thread_root_id is None:
            message.thread_root_id = message.id
            await self.session.flush()

        return message

    async def create_ai_message(
        self,
        session_id: UUID,
        content: str,
        reply_to_id: UUID | None = None,
        thread_root_id: UUID | None = None,
    ) -> ChatMessage:
        """
        Create an AI message in the chat_messages table.

        If thread_root_id is not provided, it will be automatically determined from existing messages.
        If reply_to_id is provided, it will use the thread_root_id from that message.

        Args:
            session_id: The chat session ID
            content: The message content
            reply_to_id: Optional ID of the message this is replying to
            thread_root_id: Optional ID of the root message in a thread (auto-determined if None)

        Returns:
            The created ChatMessage object
        """
        seq_no = await self.get_next_seq_no(session_id)

        # If thread_root_id is not provided, determine it automatically
        if thread_root_id is None:
            if reply_to_id is not None:
                # Get the thread_root_id from the message we're replying to
                result = await self.session.execute(
                    select(ChatMessage.thread_root_id).where(ChatMessage.id == reply_to_id)
                )
                thread_root_id = result.scalar_one_or_none()
            else:
                # Get the thread root from existing messages in the session
                thread_root_id = await self.get_thread_root_id(session_id)

        message = ChatMessage(
            session_id=session_id,
            seq_no=seq_no,
            user_id=None,  # AI messages don't have a user_id
            content=content,
            message_type=ChatMessageType.AI,
            reply_to_id=reply_to_id,
            thread_root_id=thread_root_id,
        )
        self.session.add(message)
        await self.session.flush()
        return message
