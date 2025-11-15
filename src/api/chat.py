import asyncio
import uuid

from fastapi import APIRouter, Depends

from src.api.schemas.chat import ChatRequest, ChatResponse
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.core.schema import AgentMessage
from src.dependencies import get_chat_service
from src.services.chat import ChatService

logger = logger_for("api.chat")
router = APIRouter(prefix="/chat", tags=["chat"])

# !WARNING: this endpoing is only for testing purposes. It will be removed in the future.


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a chat message",
    description="Send a message to the chat system and receive a \
    response. Supports conversation history and optional file attachments.",
)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
    user: dict = Depends(require_auth),
):
    """
    Process a chat message and return a response.

    - **message**: The user's message text (required)
    - **file**: Optional file identifier or path
    - **conversation_history**: List of previous messages for context

    Returns a chat response message.
    """

    # Call the LLM query; run in a thread to avoid blocking the event loop
    thread_id = uuid.uuid4()
    user_id = uuid.UUID(user["user_id"])
    response = await asyncio.to_thread(chat_service.query, request, thread_id, user_id)
    # If we received an AgentMessage, use its content; otherwise stringify
    if isinstance(response, AgentMessage):
        response_text = response.content
    elif response is None:
        response_text = ""
    else:
        response_text = str(response)
    logger.info(
        "chat_request",
        extra={
            "message_text": request.message,
            "has_file": bool(request.file),
            "conversation_history_length": len(request.conversation_history),
            "response_length": len(response_text) if isinstance(response_text, str) else None,
        },
    )
    return ChatResponse(response=response_text)
