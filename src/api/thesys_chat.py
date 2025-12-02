import uuid

from fastapi import APIRouter, Depends
from thesys_genui_sdk.context import write_content
from thesys_genui_sdk.fast_api import with_c1_response

from src.api.schemas.thesys_chat import (
    C1ChatRequest,
    SessionItem,
    SessionMessageConfig,
    SessionResponse,
    SessionsListResponse,
)
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.dependencies import get_thesys_chat_service
from src.services.chat_thesys_service import ThesysChatService

logger = logger_for("api.thesys_chat")
router = APIRouter(prefix="/thesys", tags=["thesys-chat"])


@router.post(
    "/session",
    summary="Create a new chat session",
    description="Creates a new chat session for the authenticated user and returns the session ID.",
    response_model=SessionResponse,
)
async def create_session(
    thesys_chat_service: ThesysChatService = Depends(get_thesys_chat_service),
    user: dict = Depends(require_auth),
):
    """
    Create a new chat session for the authenticated user.
    """
    user_id = uuid.UUID(user["user_id"])

    logger.info(
        "create_session_request",
        extra={
            "user_id": str(user_id),
        },
    )

    chat_session = await thesys_chat_service.create_session(user_id)

    return SessionResponse(
        session_id=chat_session.session_id,
        started_at=chat_session.started_at,
    )


@router.get(
    "/session",
    summary="Get all chat sessions for the authenticated user",
    description="Returns all past chat sessions for the authenticated user, sorted by most recent first.",
    response_model=SessionsListResponse,
)
async def get_sessions(
    thesys_chat_service: ThesysChatService = Depends(get_thesys_chat_service),
    user: dict = Depends(require_auth),
):
    """
    Get all chat sessions for the authenticated user, sorted by creation date (most recent first).
    """
    user_id = uuid.UUID(user["user_id"])

    logger.info(
        "get_sessions_request",
        extra={
            "user_id": str(user_id),
        },
    )

    sessions = await thesys_chat_service.get_user_sessions(user_id)

    return SessionsListResponse(
        sessions=[
            SessionItem(
                session_id=session.session_id,
                started_at=session.started_at,
            )
            for session in sessions
        ]
    )


@router.get(
    "/session/{session_id}",
    summary="Get messages for a specific session",
    description="Returns all messages for a given session ID, ordered by sequence number.",
    response_model=SessionMessageConfig,
)
async def get_session(
    session_id: str,
    thesys_chat_service: ThesysChatService = Depends(get_thesys_chat_service),
    user: dict = Depends(require_auth),
):
    """
    Get all messages for a specific chat session.
    """
    user_id = uuid.UUID(user["user_id"])
    session_uuid = uuid.UUID(session_id)

    logger.info(
        "get_session_request",
        extra={
            "session_id": session_id,
            "user_id": str(user_id),
        },
    )

    return await thesys_chat_service.get_session_messages(session_uuid, user_id)


@router.post(
    "/chat",
    summary="Streaming Thesys C1 chat endpoint",
    description=(
        "Streaming endpoint consumed by the Thesys C1Chat React component. "
        "It receives prompt, sessionId, and responseId and forwards the "
        "conversation to the C1 model, streaming tokens back as SSE."
    ),
)
@with_c1_response()
async def thesys_chat(
    request: C1ChatRequest,
    thesys_chat_service: ThesysChatService = Depends(get_thesys_chat_service),
    user: dict = Depends(require_auth),
):
    """
    Dedicated Thesys endpoint for <C1Chat>; leaves the existing /chat flow untouched.
    """
    logger.info(
        "thesys_chat_request",
        extra={
            "session_id": request.session_id,
            "user_id": user.get("user_id"),
        },
    )

    user_id = uuid.UUID(user["user_id"])

    agent_message = await thesys_chat_service.query(request, user_id=user_id)
    if agent_message and agent_message.content:
        await write_content(agent_message.content)
