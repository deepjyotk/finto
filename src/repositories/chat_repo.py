"""Chat repository - pure class for data access, no FastAPI imports"""

from uuid import UUID

from sqlalchemy import delete, func, select
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

    async def get_sessions_by_user_id_paginated(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> tuple[list[ChatSession], int]:
        """
        Get chat sessions for a user with pagination.

        Args:
            user_id: The user ID to search for
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip (based on page calculation)

        Returns:
            A tuple containing the list of ChatSession objects and the total count
        """
        total_result = await self.session.execute(
            select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
        )
        total_sessions = total_result.scalar_one()

        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total_sessions

    async def get_first_user_message_by_session_ids(
        self, session_ids: list[UUID]
    ) -> dict[UUID, str]:
        """
        For each session, return the content of the first USER message (lowest seq_no among user messages).

        Args:
            session_ids: Chat session IDs to look up

        Returns:
            Map of session_id -> message content for sessions that have at least one user message.
        """
        if not session_ids:
            return {}

        min_seq_subq = (
            select(
                ChatMessage.session_id,
                func.min(ChatMessage.seq_no).label("min_seq"),
            )
            .where(
                ChatMessage.session_id.in_(session_ids),
                ChatMessage.message_type == ChatMessageType.USER,
            )
            .group_by(ChatMessage.session_id)
        ).subquery()

        result = await self.session.execute(
            select(ChatMessage.session_id, ChatMessage.content).join(
                min_seq_subq,
                (ChatMessage.session_id == min_seq_subq.c.session_id)
                & (ChatMessage.seq_no == min_seq_subq.c.min_seq),
            )
        )
        return {row[0]: row[1] for row in result.all()}

    async def get_next_seq_no(self, session_id: UUID) -> int:
        """
        Get the next sequence number for a chat session.

        Ensures sequential numbering: User message gets seq_no=1, AI message gets seq_no=2,
        next User message gets seq_no=3, etc.

        Uses PostgreSQL advisory lock to prevent race conditions when multiple
        messages are created simultaneously for the same session.

        Args:
            session_id: The session ID

        Returns:
            The next sequence number (1 if no messages exist yet)
        """
        # Use PostgreSQL advisory lock to ensure sequential numbering
        # Convert UUID to int64 for advisory lock (using hash)
        lock_id = hash(str(session_id)) & 0x7FFFFFFF  # Ensure positive int

        # Acquire advisory lock for this session
        await self.session.execute(select(func.pg_advisory_xact_lock(lock_id)))

        # Get the max seq_no for this session
        # Since we're in the same transaction, this will see flushed but uncommitted messages
        result = await self.session.execute(
            select(func.coalesce(func.max(ChatMessage.seq_no), 0)).where(
                ChatMessage.session_id == session_id
            )
        )
        max_seq = result.scalar() or 0
        return max_seq + 1

    async def create_user_message(
        self,
        session_id: UUID,
        user_id: UUID,
        content: str,
    ) -> ChatMessage:
        """
        Create a user message in the chat_messages table.

        Args:
            session_id: The chat session ID
            user_id: The user ID (required for user messages)
            content: The message content

        Returns:
            The created ChatMessage object
        """
        seq_no = await self.get_next_seq_no(session_id)

        message = ChatMessage(
            session_id=session_id,
            seq_no=seq_no,
            user_id=user_id,
            content=content,
            message_type=ChatMessageType.USER,
        )
        self.session.add(message)
        await self.session.flush()

        return message

    async def create_ai_message(
        self,
        session_id: UUID,
        content: str,
    ) -> ChatMessage:
        """
        Create an AI message in the chat_messages table.

        Args:
            session_id: The chat session ID
            content: The message content

        Returns:
            The created ChatMessage object
        """
        seq_no = await self.get_next_seq_no(session_id)

        message = ChatMessage(
            session_id=session_id,
            seq_no=seq_no,
            user_id=None,  # AI messages don't have a user_id
            content=content,
            message_type=ChatMessageType.AI,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def get_messages_by_session_id(self, session_id: UUID) -> list[ChatMessage]:
        """
        Get all messages for a chat session, ordered by sequence number.

        Args:
            session_id: The session ID to search for

        Returns:
            List of ChatMessage objects ordered by seq_no
        """
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.seq_no.asc())
        )
        return list(result.scalars().all())

    async def delete_session(self, session_id: UUID) -> bool:
        """
        Delete a chat session and all its associated messages.

        Args:
            session_id: The session ID to delete

        Returns:
            True if session was deleted, False if session not found
        """
        # First, delete all messages for this session
        await self.session.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))

        # Then delete the session itself
        result = await self.session.execute(
            delete(ChatSession).where(ChatSession.chat_session_id == session_id)
        )
        return result.rowcount > 0
