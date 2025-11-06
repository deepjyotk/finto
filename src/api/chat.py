from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.utils.json_logging import logger_for

logger = logger_for("api.chat")
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(
        ..., description="User message to send", example="Hello, how are you?"
    )
    file: str | None = Field(
        None, description="Optional file path or identifier", example=None
    )
    conversation_history: List[str] = Field(
        default=[],
        description="Previous messages in the conversation",
        example=["Hello", "Hi there!"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "What is the weather today?",
                "file": None,
                "conversation_history": ["Hello", "Hi! How can I help you?"],
            }
        }
    }


class ChatResponse(BaseModel):
    response: str = Field(
        ..., description="AI response message", example="Hello! How can I help you?"
    )

    model_config = {
        "json_schema_extra": {
            "example": {"response": "Hello! How can I help you today?"}
        }
    }


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a chat message",
    description="Send a message to the chat system and receive a \
    response. Supports conversation history and optional file attachments.",
)
async def chat(request: ChatRequest):
    """
    Process a chat message and return a response.

    - **message**: The user's message text (required)
    - **file**: Optional file identifier or path
    - **conversation_history**: List of previous messages for context

    Returns a chat response message.
    """
    logger.info(
        "chat_request",
        extra={
            "message_text": request.message,
            "has_file": bool(request.file),
            "conversation_history_length": len(request.conversation_history),
        },
    )
    return ChatResponse(response="hello")
